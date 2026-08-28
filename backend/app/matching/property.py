"""Framework-independent contract for matching listings to properties."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.normalization.types import NormalizedListing

__all__ = ["PropertyMatcher", "PropertyMatchResult"]


@dataclass(frozen=True, slots=True)
class PropertyMatchResult:
    """Immutable result of matching a listing to a property."""

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


class PropertyMatcher(ABC):
    """Decide whether a listing identifies a property within a known building.

    A matcher owns only the property identity decision for an already-resolved
    building. It does not perform building matching or persistence, load ORM
    models, create or update Property or Listing records, ingest source data,
    normalize listings, deduplicate listings, or perform valuation.

    For current MVP data, floor, rooms, studio status, and area are descriptive
    attributes. They may help compare candidates, but they are not guaranteed
    to uniquely identify a physical apartment. A future matcher must be able
    to return an ambiguous result instead of forcing a match.
    """

    @abstractmethod
    def match(
        self,
        *,
        listing: NormalizedListing,
        building_key: str,
    ) -> PropertyMatchResult:
        """Return the property identity result within one known building."""