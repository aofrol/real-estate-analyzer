"""
Building — нормализованный физический объект недвижимости (дом).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Index, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .property import Property


class Building(Base):
    """
    Нормализованные физические объекты недвижимости (дома).
    Несколько объявлений из разных источников могут ссылаться на один building.

    location — geography(Point, 4326); ST_DWithin / ST_Distance работают в метрах.
    Порядок координат при создании точки: ST_MakePoint(longitude, latitude).
    """

    __tablename__ = "buildings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    address_raw: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Оригинальный адрес, как пришёл из источника",
    )
    address_normalized: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Нормализованный адрес после геокодирования; "
            "используется как первичный ключ идентичности здания при поиске дублей"
        ),
    )
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(200), nullable=True)
    street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    house_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    year_built: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    floors_total: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    building_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Тип дома: panel, brick, monolith, other. CHECK constraint — Decision Checklist п.6.",
    )
    # geography(Point, 4326): нативные метры в ST_DWithin / ST_Distance.
    # Nullable: геокодирование может не дать результата.
    location: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
        comment=(
            "Координаты здания (PostGIS geography, WGS84). "
            "ST_DWithin и ST_Distance работают в метрах. "
            "Порядок: ST_MakePoint(longitude, latitude)."
        ),
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
    properties: Mapped[list[Property]] = relationship(
        "Property",
        back_populates="building",
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        # GiST index on geography column; ST_DWithin uses metres natively.
        Index("ix_buildings_location", "location", postgresql_using="gist"),
        Index("ix_buildings_city", "city"),
    )
