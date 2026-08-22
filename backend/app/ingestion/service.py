"""Application service for forwarding collected listings to persistence."""

from __future__ import annotations

from typing import Any

from app.collector.base import Collector
from app.repositories.raw_listing import RawListingRepository


class IngestionService:
    """Coordinate collection and raw listing persistence."""

    def __init__(
        self,
        collector: Collector,
        repository: RawListingRepository,
    ) -> None:
        self.collector = collector
        self.repository = repository

    def run(self) -> None:
        """Collect raw listings and persist each one without transforming it."""
        for raw_listing in self.collector.collect():
            persistence_payload: dict[str, Any] = {
                "source_id": raw_listing["source_id"],
                "external_id": raw_listing["external_id"],
                "raw_data": raw_listing,
            }
            self.repository.save(persistence_payload)