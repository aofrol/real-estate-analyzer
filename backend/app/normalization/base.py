"""Framework-independent contract for listing normalization."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Normalizer(ABC):
    """Transform raw source data into canonical application-level data.

    Future implementations may canonicalize field names and convert values
    such as area, rooms, price, floor, and address fields. The normalizer
    does not access persistence, create ORM objects, collect source data,
    geocode, match entities, deduplicate listings, select comparables, or
    perform valuation.
    """

    @abstractmethod
    def normalize(self, raw_listing: dict[str, Any]) -> dict[str, Any]:
        """Return a normalized dictionary for one raw listing."""