"""Integration tests for Listing current-state and price-history orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.ingestion import ListingPersistenceOrchestrator
from app.models.listing import Listing
from app.models.listing_price_history import ListingPriceHistory
from app.models.property import Property
from app.models.source import Source
from app.normalization.types import NormalizedListing
from app.persistence import ListingPersistenceService, ListingPriceHistoryService
from app.worker.tasks.refresh import persist_refreshed_listing


def _listing(*, price: int = 200) -> NormalizedListing:
    return {
        "external_id": "source-listing-1",
        "address": "Москва, улица Ленина, 1",
        "area_sqm": 55.5,
        "rooms": 2,
        "is_studio": False,
        "floor": 5,
        "total_floors": 10,
        "asking_price_kopecks": price,
        "asking_price_per_sqm_kopecks": 4,
        "city": "Москва",
        "latitude": 55.75,
        "longitude": 37.62,
        "source_url": "https://example.test/source-listing-1",
        "building_type": "brick",
        "listed_at": datetime(2026, 8, 29),
    }


class RecordingListingPersistence:
    def __init__(
        self,
        *,
        existing: Listing | None,
        events: list[tuple[Any, ...]],
    ) -> None:
        self.existing = existing
        self.events = events

    def find_existing(
        self,
        *,
        source_key: str,
        external_id: object,
    ) -> Listing | None:
        self.events.append(("find", source_key, external_id, self.existing))
        return self.existing

    def persist(
        self,
        *,
        source_key: str,
        property_key: str,
        listing: NormalizedListing,
    ) -> Listing:
        assert self.existing is not None
        self.events.append(("persist-before", self.existing.asking_price))
        self.existing.asking_price = listing["asking_price_kopecks"]
        self.events.append(("persist-after", self.existing.asking_price))
        return self.existing


class RecordingPriceHistory:
    def __init__(self, events: list[tuple[Any, ...]]) -> None:
        self.events = events

    def record_change(
        self,
        *,
        listing: Listing,
        previous_price_kopecks: int,
        new_price_kopecks: int,
    ) -> ListingPriceHistory:
        self.events.append(
            (
                "history",
                listing,
                previous_price_kopecks,
                new_price_kopecks,
            )
        )
        return ListingPriceHistory(
            listing_id=listing.id,
            asking_price=new_price_kopecks,
        )


def _orchestrator(
    *,
    existing: Listing | None,
    events: list[tuple[Any, ...]],
) -> ListingPersistenceOrchestrator:
    return ListingPersistenceOrchestrator(
        RecordingListingPersistence(existing=existing, events=events),  # type: ignore[arg-type]
        RecordingPriceHistory(events),  # type: ignore[arg-type]
    )


def test_changed_price_is_orchestrated_in_order_and_uses_previous_value() -> None:
    events: list[tuple[Any, ...]] = []
    existing = Listing(id=uuid4(), asking_price=100)

    result = _orchestrator(existing=existing, events=events).persist(
        source_key="source-key",
        property_key="property-key",
        listing=_listing(price=200),
    )

    assert result is existing
    assert [event[0] for event in events] == [
        "find",
        "persist-before",
        "persist-after",
        "history",
    ]
    assert events[1] == ("persist-before", 100)
    assert events[2] == ("persist-after", 200)
    assert events[3][2:] == (100, 200)


def test_unchanged_price_does_not_call_history_service() -> None:
    events: list[tuple[Any, ...]] = []
    existing = Listing(id=uuid4(), asking_price=200)

    _orchestrator(existing=existing, events=events).persist(
        source_key="source-key",
        property_key="property-key",
        listing=_listing(price=200),
    )

    assert [event[0] for event in events] == [
        "find",
        "persist-before",
        "persist-after",
    ]


def test_new_listing_does_not_call_history_service() -> None:
    events: list[tuple[Any, ...]] = []

    # A real create-capable persistence double is unnecessary here: the
    # orchestration decision is based solely on the pre-write lookup result.
    class CreatePersistence(RecordingListingPersistence):
        def persist(self, **kwargs: Any) -> Listing:
            created = Listing(
                id=uuid4(),
                asking_price=kwargs["listing"]["asking_price_kopecks"],
            )
            self.events.append(("persist-create", created))
            return created

    orchestrator = ListingPersistenceOrchestrator(
        CreatePersistence(existing=None, events=events),  # type: ignore[arg-type]
        RecordingPriceHistory(events),  # type: ignore[arg-type]
    )

    result = orchestrator.persist(
        source_key="source-key",
        property_key="property-key",
        listing=_listing(price=200),
    )

    assert result.asking_price == 200
    assert [event[0] for event in events] == ["find", "persist-create"]


def test_history_failure_crosses_boundary_without_transaction_ownership() -> None:
    events: list[tuple[Any, ...]] = []
    source_id = uuid4()
    property_id = uuid4()
    existing = Listing(
        id=uuid4(),
        source_id=source_id,
        property_id=property_id,
        external_id="source-listing-1",
        asking_price=100,
        asking_price_per_sqm=2,
    )
    source = Source(
        id=source_id,
        name="Test source",
        adapter_class="app.sources.mock.MockAdapter",
    )
    property_row = Property(
        id=property_id,
        building_id=uuid4(),
        rooms=2,
        area_total=55.5,
        is_studio=False,
    )

    class ScalarResult:
        def one_or_none(self) -> Listing:
            return existing

    class SharedSession:
        def __init__(self) -> None:
            self.added: list[object] = []
            self.commit_calls = 0
            self.rollback_calls = 0
            self.close_calls = 0

        def get(self, model: type[object], key: UUID) -> object | None:
            events.append(("get", model, key))
            if model is Source:
                return source
            if model is Property:
                return property_row
            return None

        def scalars(self, statement: object) -> ScalarResult:
            events.append(("find", existing.asking_price))
            return ScalarResult()

        def add(self, row: object) -> None:
            self.added.append(row)
            events.append(("add", type(row)))

        def flush(self) -> None:
            if self.added and isinstance(self.added[-1], ListingPriceHistory):
                events.append(("history-flush", existing.asking_price))
                raise RuntimeError("history persistence failed")
            events.append(("listing-flush", existing.asking_price))

        def commit(self) -> None:
            self.commit_calls += 1

        def rollback(self) -> None:
            self.rollback_calls += 1
            existing.asking_price = 100
            self.added.clear()

        def close(self) -> None:
            self.close_calls += 1

    session = SharedSession()

    with pytest.raises(RuntimeError, match="history persistence failed"):
        ListingPersistenceOrchestrator(
            ListingPersistenceService(session),  # type: ignore[arg-type]
            ListingPriceHistoryService(session),  # type: ignore[arg-type]
        ).persist(
            source_key=str(source_id),
            property_key=str(property_id),
            listing=_listing(price=200),
        )

    assert [event[0] for event in events] == [
        "find",
        "get",
        "get",
        "find",
        "listing-flush",
        "add",
        "history-flush",
    ]
    assert existing.asking_price == 200
    assert isinstance(session.added[0], ListingPriceHistory)
    assert session.commit_calls == 0
    assert session.rollback_calls == 0
    assert session.close_calls == 0

    # The caller, not the orchestration layer, decides how to abort the
    # enclosing transaction after the error.
    session.rollback()
    assert session.rollback_calls == 1
    assert existing.asking_price == 100
    assert session.added == []


def test_worker_refresh_builds_orchestrator_on_the_caller_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = object()
    expected = Listing(id=uuid4(), asking_price=200)
    calls: list[tuple[Any, ...]] = []

    class Orchestrator:
        def persist(self, **kwargs: Any) -> Listing:
            calls.append(("persist", kwargs))
            return expected

    def from_session(received_session: object) -> Orchestrator:
        calls.append(("from-session", received_session))
        return Orchestrator()

    monkeypatch.setattr(
        ListingPersistenceOrchestrator,
        "from_session",
        from_session,
    )

    result = persist_refreshed_listing(
        session=session,  # type: ignore[arg-type]
        source_key="source-key",
        property_key="property-key",
        listing=_listing(),
    )

    assert result is expected
    assert calls[0] == ("from-session", session)
    assert calls[1][0] == "persist"


def test_lookup_can_be_used_before_listing_mutation() -> None:
    """The real service exposes the pre-write identity lookup boundary."""
    source_id = UUID("00000000-0000-0000-0000-000000000001")
    existing = Listing(
        id=uuid4(),
        source_id=source_id,
        external_id="source-listing-1",
        asking_price=100,
    )

    class Session:
        def scalars(self, statement: object):
            class Result:
                def one_or_none(self) -> Listing:
                    return existing

            return Result()

    assert ListingPersistenceService(Session()).find_existing(
        source_key=str(source_id),
        external_id="source-listing-1",
    ) is existing