"""
RawListing — буфер сырых данных из источников.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .source import Source


class RawListing(Base):
    """
    Буфер сырых данных из источников.
    Хранит оригинальный JSON-payload нетронутым.
    После нормализации помечается is_processed = True.
    Строки не удаляются — обеспечивают аудитность и возможность повторной нормализации.
    """

    __tablename__ = "raw_listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # FK1: RESTRICT — нельзя удалить источник, имеющий собранные данные.
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Идентификатор объявления в системе источника",
    )
    raw_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Полный оригинальный payload от источника (неизменяем после записи)",
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Время сбора данных",
    )
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Флаг: нормализовано ли объявление в listings",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    source: Mapped[Source] = relationship(
        "Source",
        back_populates="raw_listings",
    )

    # ── Constraints & Indexes ──────────────────────────────────────────────────
    __table_args__ = (
        # UQ: предотвращение повторного сбора того же объявления из того же источника.
        UniqueConstraint("source_id", "external_id", name="uq_raw_listings_source_external"),
        # Composite: быстрый выбор необработанных объявлений; collected_at для упорядочивания.
        Index("ix_raw_listings_processed_collected", "is_processed", "collected_at"),
    )
