"""
ValuationComparable — объявление-аналог, использованное в конкретной оценке.

Snapshot-таблица: snapshot-поля фиксируют значения на момент оценки и не зависят
от последующих изменений listings/properties/buildings.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Double, ForeignKey, Index, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDPkMixin

if TYPE_CHECKING:
    from .listing import Listing
    from .valuation_result import ValuationResult


class ValuationComparable(UUIDPkMixin, Base):
    """
    Объявления, использованные в конкретной оценке.

    Snapshot-поля (_snapshot) фиксируют значения comparable на момент оценки.
    FK listing_id сохраняется для audit/lineage, но расчёт опирается исключительно
    на snapshot-поля. Строки не изменяются после вставки.

    Денежные поля — BIGINT в kopecks; площадь — NUMERIC(8,2) в м²;
    расстояние — DOUBLE PRECISION в метрах.
    """

    __tablename__ = "valuation_comparables"

    valuation_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # FK8: CASCADE — comparables без результата оценки бессмысленны.
        ForeignKey("valuation_results.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    # FK9: RESTRICT — нельзя удалить объявление, использованное в оценке.
    # Snapshot-поля хранят значения независимо от состояния listing после оценки.
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="FK → listings.id для audit/lineage; расчёт не зависит от текущего состояния строки listings",
    )

    # ── Ранг и вес ────────────────────────────────────────────────────────────
    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment=(
            "Порядковый номер comparable в наборе, отсортированном по similarity_score DESC. "
            "Первый по схожести = 1."
        ),
    )
    weight: Mapped[float] = mapped_column(
        Double(),
        nullable=False,
        comment=(
            "Вес comparable в расчёте weighted_asking_price. "
            "Сумма весов по всему valuation_result_id = 1.0."
        ),
    )
    similarity_score: Mapped[float] = mapped_column(
        Double(),
        nullable=False,
        comment="Итоговый взвешенный score схожести, 0.0–1.0",
    )

    # ── Snapshot-поля: значения comparable на момент оценки ──────────────────
    # Обязательны для воспроизводимости расчёта. NOT NULL кроме floor и building_type.
    distance_m: Mapped[float] = mapped_column(
        Double(),
        nullable=False,
        comment=(
            "Расстояние от comparable до объекта оценки, метры (geography ST_Distance). "
            "Компонент similarity_score и отображается пользователю."
        ),
    )
    asking_price_snapshot: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="listings.asking_price на момент оценки, kopecks",
    )
    asking_price_per_sqm_snapshot: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment=(
            "listings.asking_price_per_sqm на момент оценки, kopecks. "
            "Ключевое поле: IQR-фильтр и weighted median опираются на него."
        ),
    )
    area_total_snapshot: Mapped[float] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        comment="properties.area_total на момент оценки, м²",
    )
    rooms_snapshot: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="properties.rooms на момент оценки",
    )
    floor_snapshot: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="properties.floor на момент оценки; NULL если не указан",
    )
    building_type_snapshot: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="buildings.building_type на момент оценки; NULL если не определён",
    )
    source_id_snapshot: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment=(
            "listings.source_id на момент оценки. "
            "Идентифицирует происхождение comparable без JOIN."
        ),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    valuation_result: Mapped[ValuationResult] = relationship(
        "ValuationResult",
        back_populates="comparables",
    )
    listing: Mapped[Listing] = relationship(
        "Listing",
        back_populates="valuation_comparables",
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        # FK lookup: загрузка всех comparables оценки.
        Index("ix_valuation_comparables_result_id", "valuation_result_id"),
        # Composite: получение comparables в порядке ранга для отображения.
        Index("ix_valuation_comparables_result_rank", "valuation_result_id", "rank"),
        # Audit: в каких оценках использовалось объявление.
        Index("ix_valuation_comparables_listing_id", "listing_id"),
    )
