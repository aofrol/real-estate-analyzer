"""Framework-independent contract for listing normalization."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .types import NormalizedListing


class Normalizer(ABC):
    """Transform raw source data into canonical application-level data.

    Future implementations may canonicalize field names and convert values
    such as area, rooms, price, floor, and address fields. The normalizer
    does not access persistence, create ORM objects, collect source data, make
    API requests, geocode, match entities, deduplicate listings, select
    comparables, or perform valuation. Its result is a NormalizedListing
    dictionary, not an ORM object.
    """

    @abstractmethod
    def normalize(self, raw_listing: dict[str, Any]) -> NormalizedListing:
        """Return a canonical NormalizedListing for one raw listing."""