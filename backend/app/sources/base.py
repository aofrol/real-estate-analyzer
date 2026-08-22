"""Abstract interface for external real-estate source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SourceAdapter(ABC):
    """Fetch and initially parse data from one external source.

    An adapter owns source-specific I/O and parsing only. It must not access
    the database, construct ORM objects, normalize records into domain models,
    or perform deduplication.
    """

    @abstractmethod
    def collect(self) -> dict[str, Any]:
        """Fetch one or more source records in the source's raw format."""

    @abstractmethod
    def parse(self, raw_listing: dict[str, Any]) -> dict[str, Any]:
        """Parse one raw source record without normalizing or deduplicating it."""