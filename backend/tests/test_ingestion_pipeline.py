"""End-to-end in-memory test for the ingestion pipeline."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

import pytest

from app.collector.mock import MockCollector
from app.ingestion.service import IngestionService
from app.repositories.raw_listing import RawListingRepository
from app.sources.mock import MockAdapter


class FakeRawListingRepository(RawListingRepository):
    """Capture repository payloads without opening a database connection."""

    def __init__(self) -> None:
        self.saved_payloads: list[dict[str, Any]] = []

    def save(
        self,
        *,
        source_id: UUID,
        external_id: str,
        raw_data: dict[str, Any],
    ) -> None:
        self.saved_payloads.append(
            {
                "source_id": source_id,
                "external_id": external_id,
                "raw_data": raw_data,
            }
        )


def test_mock_ingestion_pipeline_saves_raw_listing(monkeypatch) -> None:
    """MockAdapter data flows through MockCollector into the fake repository."""
    source_id = UUID("00000000-0000-0000-0000-000000000001")
    adapter = MockAdapter()
    raw_listing = adapter.collect()[0]
    original_raw_listing = deepcopy(raw_listing)
    monkeypatch.setattr(adapter, "collect", lambda: [raw_listing])

    collector = MockCollector(adapter)
    repository = FakeRawListingRepository()
    service = IngestionService(collector, repository, source_id)

    service.run()

    assert len(repository.saved_payloads) == 1
    saved_payload = repository.saved_payloads[0]
    assert saved_payload["source_id"] == source_id
    assert saved_payload["external_id"] == "mock-001"
    assert saved_payload["raw_data"] is raw_listing
    assert saved_payload["raw_data"]["external_id"] == "mock-001"
    assert "source_id" not in saved_payload["raw_data"]
    assert raw_listing == original_raw_listing


@pytest.mark.parametrize("invalid_value", ["", "   ", 123])
def test_ingestion_rejects_invalid_external_id(
    monkeypatch,
    invalid_value: object,
) -> None:
    """Invalid external IDs fail at the ingestion boundary."""
    source_id = UUID("00000000-0000-0000-0000-000000000001")
    adapter = MockAdapter()
    raw_listing = adapter.collect()[0]
    raw_listing["external_id"] = invalid_value
    monkeypatch.setattr(adapter, "collect", lambda: [raw_listing])

    service = IngestionService(
        MockCollector(adapter),
        FakeRawListingRepository(),
        source_id,
    )

    with pytest.raises(ValueError, match="external_id"):
        service.run()


def test_ingestion_rejects_missing_external_id(monkeypatch) -> None:
    """A collected payload must contain its external identity."""
    source_id = UUID("00000000-0000-0000-0000-000000000001")
    adapter = MockAdapter()
    raw_listing = adapter.collect()[0]
    raw_listing.pop("external_id")
    monkeypatch.setattr(adapter, "collect", lambda: [raw_listing])

    service = IngestionService(
        MockCollector(adapter),
        FakeRawListingRepository(),
        source_id,
    )

    with pytest.raises(ValueError, match="external_id"):
        service.run()