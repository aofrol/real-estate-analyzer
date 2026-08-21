"""
Building — нормализованный физический объект недвижимости (дом).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPkMixin

if TYPE_CHECKING:
    from .property import Property


class Building(UUIDPkMixin, Base):
    """
    Нормализованные физические объекты недвижимости (дома).
    Несколько объявлений из разных источников могут ссылаться на один building.

    location — geography(Point, 4326); ST_DWithin / ST_Distance работают в метрах.
    Порядок координат при создании точки: ST_MakePoint(longitude, latitude).
    """

    __tablename__ = "buildings"

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
    # spatial_index=False: explicit GiST index defined below in __table_args__
    # to avoid the duplicate auto-index GeoAlchemy2 would otherwise create.
    location: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
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
        # Explicit GiST index on geography column; ST_DWithin uses metres natively.
        # spatial_index=False on the column prevents GeoAlchemy2 from creating
        # a duplicate auto-index alongside this one.
        Index("ix_buildings_location", "location", postgresql_using="gist"),
        Index("ix_buildings_city", "city"),
    )
