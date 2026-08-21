"""
Source — реестр источников данных (сайтов-агрегаторов).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPkMixin

if TYPE_CHECKING:
    from .listing import Listing
    from .raw_listing import RawListing


class Source(UUIDPkMixin, Base):
    """
    Реестр источников данных. Каждый Source Adapter регистрируется здесь.
    Служит точкой конфигурации и audit trail происхождения объявлений.
    """

    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Человекочитаемое имя источника (уникальное)",
    )
    base_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Базовый URL сайта-источника",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Флаг активности; неактивные источники не опрашиваются",
    )
    adapter_class: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Python fully-qualified class name адаптера",
    )
    config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Конфигурация, специфичная для адаптера (timeout, headers и т.п.)",
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
    raw_listings: Mapped[list[RawListing]] = relationship(
        "RawListing",
        back_populates="source",
    )
    listings: Mapped[list[Listing]] = relationship(
        "Listing",
        back_populates="source",
    )

    # ── Constraints & Indexes ──────────────────────────────────────────────────
    __table_args__ = (
        # Named UniqueConstraint consistent with project naming convention.
        UniqueConstraint("name", name="uq_sources_name"),
        Index("ix_sources_is_active", "is_active"),
    )
