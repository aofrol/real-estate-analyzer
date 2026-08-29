"""Framework-independent property candidate contracts."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.normalization.types import NormalizedListing

__all__ = ["PropertyCandidate", "PropertyCandidateProvider"]


@dataclass(frozen=True, slots=True)
class PropertyCandidate:
    """Candidate property data supplied to a matcher."""

    key: str
    floor: int | None
    rooms: int | None
    is_studio: bool
    area_sqm: float

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("key must be a non-empty string")

        if self.floor is not None and (
            isinstance(self.floor, bool) or not isinstance(self.floor, int)
        ):
            raise ValueError("floor must be an int or None")

        if self.rooms is not None and (
            isinstance(self.rooms, bool)
            or not isinstance(self.rooms, int)
            or self.rooms < 0
        ):
            raise ValueError("rooms must be a non-negative int or None")

        if not isinstance(self.is_studio, bool):
            raise ValueError("is_studio must be a bool")

        if (
            isinstance(self.area_sqm, bool)
            or not isinstance(self.area_sqm, (int, float))
            or not math.isfinite(self.area_sqm)
            or self.area_sqm <= 0
        ):
            raise ValueError("area_sqm must be a finite number greater than 0")


class PropertyCandidateProvider(ABC):
    """Supply plausible property candidates within a known building."""

    @abstractmethod
    def get_candidates(
        self,
        *,
        listing: NormalizedListing,
        building_key: str,
    ) -> list[PropertyCandidate]:
        """Return candidates without deciding which candidate matches."""