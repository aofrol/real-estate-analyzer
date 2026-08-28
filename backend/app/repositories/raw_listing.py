"""Framework-independent persistence contract for raw listings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class RawListingRepository(ABC):
    """Define persistence operations for raw listing payloads."""

    @abstractmethod
    def save(
        self,
        *,
        source_id: UUID,
        external_id: str,
        raw_data: dict[str, Any],
    ) -> None:
        """Persist one raw listing payload with application-supplied identity."""