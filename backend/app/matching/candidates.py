"""Framework-independent building candidate contracts."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.normalization.types import NormalizedListing


@dataclass(frozen=True, slots=True)
class BuildingCandidate:
    """Candidate building data supplied to a matcher."""

    key: str
    address_normalized: str
    city: str | None
    latitude: float | None
    longitude: float | None
    building_type: str | None
    floors_total: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("key must be a non-empty string")
        if not isinstance(self.address_normalized, str) or not self.address_normalized.strip():
            raise ValueError("address_normalized must be a non-empty string")

        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")

        if self.latitude is not None:
            if (
                not isinstance(self.latitude, (int, float))
                or not math.isfinite(self.latitude)
                or not -90.0 <= self.latitude <= 90.0
            ):
                raise ValueError("latitude must be between -90 and 90")
            if (
                not isinstance(self.longitude, (int, float))
                or not math.isfinite(self.longitude)
                or not -180.0 <= self.longitude <= 180.0
            ):
                raise ValueError("longitude must be between -180 and 180")

        if self.floors_total is not None and (
            not isinstance(self.floors_total, int) or self.floors_total <= 0
        ):
            raise ValueError("floors_total must be greater than 0")


class BuildingCandidateProvider(ABC):
    """Supply plausible building candidates without deciding the match."""

    @abstractmethod
    def get_candidates(
        self,
        listing: NormalizedListing,
    ) -> list[BuildingCandidate]:
        """Return candidates for one normalized listing."""