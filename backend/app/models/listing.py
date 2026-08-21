"""
Listing — центральная таблица объявлений о продаже/аренде.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .listing_price_history import ListingPriceHistory
    from .property import Property
    from .source import Source
    from .valuation_comparable import ValuationComparable


class Listing(Base):
    """
    Центральная таблица: объявление о продаже/аренде.

    Строки НИКОГДА не удаляются. Дубликаты помечаются duplicate_of_id, но остаются в таблице.
    ComparableEngine работает только с WHERE duplicate_of_id IS NULL AND status = 'active'.

    Все денежные поля — BIGINT в копейках (1 RUB = 100 kopecks).
    Конвертация только в Pydantic API-слое.

    location — geography(Point, 4326); ST_DWithin / ST_Distance работают в метрах.
    """

    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # FK3: RESTRICT — нельзя удалить квартиру с объявлениями.
        ForeignKey("properties.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # FK4: RESTRICT — нельзя удалить источник с объявлениями.
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="ID объявления в системе источника",
    )
    url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Прямая ссылка на объявление",
    )
    asking_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Запрашиваемая цена, kopecks. Цена продавца, не подтверждённая сделка.",
    )
    asking_price_per_sqm: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment=(
            "Цена за м², kopecks. "
            "= asking_price / area_total, вычисляется при нормализации (ROUND_HALF_UP)."
        ),
    )
    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'active'"),
        comment=(
            "Состояние объявления: active, sold, removed. "
            "CHECK constraint — Decision Checklist п.6 (открыт)."
        ),
    )
    listed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата публикации объявления (по данным источника)",
    )
    removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата снятия объявления (NULL, если ещё активно)",
    )
    # geography(Point, 4326): нативные метры в ST_DWithin / ST_Distance.
    # Nullable: геокодирование может не дать результата.
    location: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
        comment=(
            "Координаты объявления (PostGIS geography, WGS84). "
            "Может отличаться от buildings.location. "
            "Порядок: ST_MakePoint(longitude, latitude)."
        ),
    )
    # FK5: SET NULL — если «оригинал» удалён, дубликат становится самостоятельным.
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        comment="FK → listings.id; указывает на каноническое объявление. NULL = не дубликат.",
    )
    extra: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Дополнительные атрибуты, специфичные для источника",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    property: Mapped[Property] = relationship(
        "Property",
        back_populates="listings",
    )
    source: Mapped[Source] = relationship(
        "Source",
        back_populates="listings",
    )
    price_history: Mapped[list[ListingPriceHistory]] = relationship(
        "ListingPriceHistory",
        back_populates="listing",
    )
    valuation_comparables: Mapped[list[ValuationComparable]] = relationship(
        "ValuationComparable",
        back_populates="listing",
    )
    # Self-referential: этот listing является дубликатом другого (многие → один).
    duplicate_of: Mapped[Listing | None] = relationship(
        "Listing",
        foreign_keys="[Listing.duplicate_of_id]",
        back_populates="duplicates",
        remote_side="Listing.id",
    )
    # Self-referential: все listings, считающие этот каноническим (один → многие).
    duplicates: Mapped[list[Listing]] = relationship(
        "Listing",
        foreign_keys="[Listing.duplicate_of_id]",
        back_populates="duplicate_of",
    )

    # ── Constraints & Indexes ──────────────────────────────────────────────────
    __table_args__ = (
        # UQ: каноническая идентичность объявления внутри источника.
        UniqueConstraint("source_id", "external_id", name="uq_listings_source_external"),
        # Partial GiST на geography: покрывает ядро запроса ComparableEngine.
        # ST_DWithin(location, target, radius_m) работает в метрах.
        # Объединяет пространственный фильтр с бизнес-условиями в одном индексе.
        Index(
            "ix_listings_location_active",
            "location",
            postgresql_using="gist",
            postgresql_where=text("duplicate_of_id IS NULL AND status = 'active'"),
        ),
        # BTREE на status для non-spatial запросов.
        Index("ix_listings_status", "status"),
        # FK lookup + сортировка при Celery refresh.
        Index("ix_listings_listed_at", "listed_at"),
        Index("ix_listings_property_id", "property_id"),
        # Partial: поиск всех дубликатов конкретного объявления.
        Index(
            "ix_listings_duplicate_of_id_notnull",
            "duplicate_of_id",
            postgresql_where=text("duplicate_of_id IS NOT NULL"),
        ),
    )
