"""
Property — конкретная квартира/юнит внутри здания.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, SmallInteger, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .building import Building
    from .listing import Listing


class Property(Base):
    """
    Конкретная квартира/юнит внутри здания: этаж, количество комнат, площади.
    Промежуточный слой между зданием (Building) и объявлением (Listing).

    Одно здание содержит N квартир (Building 1→N Property).
    Одна квартира может иметь N объявлений из разных источников (Property 1→N Listing).

    Deduplication strategy (matching при нормализации): см. docs/database-design-v0.1.md,
    раздел 13. Строгий UNIQUE не применяется; matching-логика реализуется в Normalizer (Task #4).
    """

    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # FK2: RESTRICT — нельзя удалить здание с квартирами.
        ForeignKey("buildings.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    floor: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="Этаж квартиры",
    )
    rooms: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Количество комнат; 0 = студия",
    )
    area_total: Mapped[float] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        comment="Общая площадь, м²",
    )
    area_living: Mapped[float | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Жилая площадь, м²",
    )
    area_kitchen: Mapped[float | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Площадь кухни, м²",
    )
    is_studio: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Явный флаг студии (дублирует rooms = 0 для читаемости)",
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
    building: Mapped[Building] = relationship(
        "Building",
        back_populates="properties",
    )
    listings: Mapped[list[Listing]] = relationship(
        "Listing",
        back_populates="property",
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        # FK lookup
        Index("ix_properties_building_id", "building_id"),
        # Composite: поиск схожих квартир по комнатам и площади в ComparableEngine.
        Index("ix_properties_rooms_area_total", "rooms", "area_total"),
    )
