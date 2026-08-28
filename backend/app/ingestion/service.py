"""Application service for forwarding collected listings to persistence."""

from __future__ import annotations

from uuid import UUID

from app.collector.base import Collector
from app.repositories.raw_listing import RawListingRepository


class IngestionService:
    """Coordinate collection and raw listing persistence."""

    def __init__(
        self,
        collector: Collector,
        repository: RawListingRepository,
        source_id: UUID,
    ) -> None:
        self.collector = collector
        self.repository = repository
        self._source_id = source_id

    def run(self) -> None:
        """Collect raw listings and persist each one without transforming it."""
        for raw_listing in self.collector.collect():
            external_id = raw_listing.get("external_id")
            if not isinstance(external_id, str) or not external_id.strip():
                raise ValueError("external_id must be non-empty")

            self.repository.save(
                source_id=self._source_id,
                external_id=external_id,
                raw_data=raw_listing,
            )