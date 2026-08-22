"""Framework-independent persistence contract for raw listings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RawListingRepository(ABC):
    """Define persistence operations for raw listing payloads."""

    @abstractmethod
    def save(self, raw_listing: dict[str, Any]) -> None:
        """Persist one raw listing payload."""