"""Framework-independent contract for matching listings to buildings."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.normalization.types import NormalizedListing


@dataclass(frozen=True, slots=True)
class BuildingMatchResult:
    """Immutable result of matching a normalized listing to a building."""

    matched: bool
    candidate_key: str | None
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("confidence must be between 0.0 and 1.0")

        if self.matched:
            if not isinstance(self.candidate_key, str) or not self.candidate_key.strip():
                raise ValueError("candidate_key must be non-empty when matched")
        elif self.candidate_key is not None:
            raise ValueError("candidate_key must be None when unmatched")

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty")


class BuildingMatcher(ABC):
    """Decide whether a normalized listing matches a known building candidate.

    A matcher owns only the decision according to its matching strategy. It
    does not collect listings, normalize data, geocode, create or update
    buildings, manage database transactions, match properties, persist
    listings, detect duplicates, select comparables, or perform valuation.
    """

    @abstractmethod
    def match(self, listing: NormalizedListing) -> BuildingMatchResult:
        """Return the match result for one normalized listing."""