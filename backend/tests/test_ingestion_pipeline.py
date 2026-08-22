"""End-to-end in-memory test for the ingestion pipeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.collector.mock import MockCollector
from app.ingestion.service import IngestionService
from app.repositories.raw_listing import RawListingRepository
from app.sources.mock import MockAdapter


class FakeRawListingRepository(RawListingRepository):
    """Capture repository payloads without opening a database connection."""

    def __init__(self) -> None:
        self.saved_payloads: list[dict[str, Any]] = []

    def save(self, raw_listing: dict[str, Any]) -> None:
        self.saved_payloads.append(raw_listing)


def test_mock_ingestion_pipeline_saves_raw_listing(monkeypatch) -> None:
    """MockAdapter data flows through MockCollector into the fake repository."""
    source_id = UUID("00000000-0000-0000-0000-000000000001")
    adapter = MockAdapter()
    original_collect = adapter.collect
    raw_listing = original_collect()[0]
    raw_listing["source_id"] = source_id

    monkeypatch.setattr(adapter, "collect", lambda: [raw_listing])

    collector = MockCollector(adapter)
    repository = FakeRawListingRepository()
    service = IngestionService(collector, repository)

    service.run()

    assert len(repository.saved_payloads) == 1
    saved_payload = repository.saved_payloads[0]
    assert saved_payload["source_id"] == source_id
    assert saved_payload["external_id"] == "mock-001"
    assert saved_payload["raw_data"] is raw_listing
    assert saved_payload["raw_data"]["external_id"] == "mock-001"