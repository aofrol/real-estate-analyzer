"""
ListingPriceHistory — хронология изменений цены объявления.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, desc, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPkMixin

if TYPE_CHECKING:
    from .listing import Listing


class ListingPriceHistory(UUIDPkMixin, Base):
    """
    Хронология изменений цены для конкретного объявления.
    Создаётся при каждом обновлении asking_price.
    Строки append-only: не изменяются и не удаляются (если Listing не удалён, но Listing тоже не удаляется).

    asking_price — BIGINT в kopecks.
    """

    __tablename__ = "listing_price_history"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # FK6: CASCADE — история без объявления лишена смысла.
        # Listing никогда не удаляется, поэтому CASCADE носит защитный характер.
        ForeignKey("listings.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    asking_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Зафиксированная цена в kopecks на момент записи",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Время фиксации цены (момент обнаружения изменения коллектором)",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    listing: Mapped[Listing] = relationship(
        "Listing",
        back_populates="price_history",
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        # Composite: хронологический ряд цен — listing_id equality + recorded_at DESC
        # для запросов ORDER BY recorded_at DESC (последние изменения цены первыми).
        Index(
            "ix_listing_price_history_listing_recorded",
            "listing_id",
            desc("recorded_at"),
        ),
    )
