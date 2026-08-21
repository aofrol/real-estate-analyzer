"""
ValuationResult — immutable результат оценки рыночной стоимости.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Double, ForeignKey, Index, Integer, String, desc, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPkMixin

if TYPE_CHECKING:
    from .search_request import SearchRequest
    from .valuation_comparable import ValuationComparable


class ValuationResult(UUIDPkMixin, Base):
    """
    Результат оценки: набор статистик в kopecks, версия алгоритма и параметры запуска.
    Привязан к одному SearchRequest. Immutable snapshot на момент вычисления.

    Строка не изменяется после вставки.
    Все денежные поля — BIGINT в kopecks.

    algorithm_version + parameters обязательны для аудита и воспроизводимости:
    они позволяют установить, какой версией алгоритма и с какими параметрами
    получен каждый результат, независимо от текущих env-переменных.
    """

    __tablename__ = "valuation_results"

    search_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # FK7: RESTRICT — запрос нужен для Celery refresh; удаление заблокировано результатом.
        ForeignKey("search_requests.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    algorithm_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment=(
            "Версия алгоритма оценки, напр. 'v1.0'. "
            "Обязательна для аудита и различения результатов разных версий логики."
        ),
    )
    parameters: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment=(
            "Параметры конкретного запуска оценки: radius_m, iqr_multiplier, "
            "max_comparables, веса компонентов и другие влияющие настройки. "
            "Позволяет воспроизвести расчёт независимо от текущих env-переменных."
        ),
    )
    # ── Статистики (kopecks) ──────────────────────────────────────────────────
    median_asking_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Медианная цена по comparables, kopecks",
    )
    mean_asking_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Средняя цена, kopecks",
    )
    min_asking_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Минимальная цена, kopecks (вторичная статистика)",
    )
    max_asking_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Максимальная цена, kopecks (вторичная статистика)",
    )
    p25_asking_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="25-й перцентиль, kopecks (нижняя граница диапазона)",
    )
    p75_asking_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="75-й перцентиль, kopecks (верхняя граница диапазона)",
    )
    median_price_per_sqm: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Медианная цена за м², kopecks",
    )
    mean_price_per_sqm: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Средняя цена за м², kopecks",
    )
    weighted_asking_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Основная оценка: weighted_median_price_per_sqm × area, kopecks",
    )
    # ── Качество ─────────────────────────────────────────────────────────────
    confidence_score: Mapped[float] = mapped_column(
        Double(),
        nullable=False,
        comment="Внутренний score 0.0–1.0; в UI отображается как цветовой badge",
    )
    comparables_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Количество использованных объявлений (после IQR-фильтра)",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Момент вычисления оценки",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    search_request: Mapped[SearchRequest] = relationship(
        "SearchRequest",
        back_populates="valuation_results",
    )
    comparables: Mapped[list[ValuationComparable]] = relationship(
        "ValuationComparable",
        back_populates="valuation_result",
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        # FK lookup: загрузка всех результатов по запросу.
        Index("ix_valuation_results_search_request_id", "search_request_id"),
        # Получение последней оценки по запросу (ORDER BY computed_at DESC).
        Index("ix_valuation_results_computed_at", desc("computed_at")),
    )
