"""
SearchRequest — параметры пользовательского запроса оценки.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Double, Index, Numeric, SmallInteger, Text, desc, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPkMixin

if TYPE_CHECKING:
    from .valuation_result import ValuationResult


class SearchRequest(UUIDPkMixin, Base):
    """
    Параметры каждого пользовательского запроса оценки.
    Служит anchor для Valuation Result и источником адресов для Celery refresh.

    lat/lon — DOUBLE PRECISION; координаты результата геокодирования.
    """

    __tablename__ = "search_requests"

    address_raw: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Адрес в виде, введённом пользователем",
    )
    address_normalized: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Нормализованный адрес после геокодирования",
    )
    lat: Mapped[float | None] = mapped_column(
        Double(),
        nullable=True,
        comment="Широта, результат геокодирования (DOUBLE PRECISION)",
    )
    lon: Mapped[float | None] = mapped_column(
        Double(),
        nullable=True,
        comment="Долгота (DOUBLE PRECISION)",
    )
    rooms: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Количество комнат (0 = студия)",
    )
    area: Mapped[float] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        comment="Площадь, м²",
    )
    floor: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="Этаж",
    )
    params: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Прочие параметры запроса (расширяемость)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Используется Celery для определения «недавних» локаций",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    valuation_results: Mapped[list[ValuationResult]] = relationship(
        "ValuationResult",
        back_populates="search_request",
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        # Celery refresh: выбор недавних локаций (ORDER BY created_at DESC LIMIT N).
        Index("ix_search_requests_created_at", desc("created_at")),
    )
