"""Database-free tests for ListingPriceHistoryService."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.models.listing import Listing
from app.models.listing_price_history import ListingPriceHistory
from app.persistence import ListingPriceHistoryService


class FakeSession:
    """Record ORM operations without opening a database connection."""

    def __init__(self) -> None:
        self.added: list[ListingPriceHistory] = []
        self.flush_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def add(self, history_row: ListingPriceHistory) -> None:
        self.added.append(history_row)

    def flush(self) -> None:
        self.flush_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1


def _listing(listing_id: UUID | None = None) -> Listing:
    return Listing(id=listing_id if listing_id is not None else uuid4())


def test_changed_price_creates_one_history_row_for_new_price() -> None:
    session = FakeSession()
    listing = _listing()

    result = ListingPriceHistoryService(session).record_change(
        listing=listing,
        previous_price_kopecks=1_250_000_000,
        new_price_kopecks=1_300_000_000,
    )

    assert result is session.added[0]
    assert result.listing_id == listing.id
    assert result.asking_price == 1_300_000_000
    assert len(session.added) == 1
    assert session.flush_calls == 1


def test_changed_price_returns_created_history_row() -> None:
    session = FakeSession()

    result = ListingPriceHistoryService(session).record_change(
        listing=_listing(),
        previous_price_kopecks=100,
        new_price_kopecks=101,
    )

    assert result is not None
    assert result is session.added[0]


def test_unchanged_price_returns_none_without_side_effects() -> None:
    session = FakeSession()

    result = ListingPriceHistoryService(session).record_change(
        listing=_listing(),
        previous_price_kopecks=100,
        new_price_kopecks=100,
    )

    assert result is None
    assert session.added == []
    assert session.flush_calls == 0


def test_initial_listing_creation_is_not_recorded_by_this_service() -> None:
    session = FakeSession()
    listing = _listing()

    result = ListingPriceHistoryService(session).record_change(
        listing=listing,
        previous_price_kopecks=100,
        new_price_kopecks=100,
    )

    assert result is None
    assert session.added == []


def test_listing_is_not_mutated() -> None:
    session = FakeSession()
    listing = _listing()
    before = {
        "id": listing.id,
        "asking_price": listing.asking_price,
        "asking_price_per_sqm": listing.asking_price_per_sqm,
        "duplicate_of_id": listing.duplicate_of_id,
    }

    ListingPriceHistoryService(session).record_change(
        listing=listing,
        previous_price_kopecks=100,
        new_price_kopecks=101,
    )

    assert {
        "id": listing.id,
        "asking_price": listing.asking_price,
        "asking_price_per_sqm": listing.asking_price_per_sqm,
        "duplicate_of_id": listing.duplicate_of_id,
    } == before


def test_price_inputs_are_not_modified() -> None:
    session = FakeSession()
    previous_price = 100
    new_price = 101

    ListingPriceHistoryService(session).record_change(
        listing=_listing(),
        previous_price_kopecks=previous_price,
        new_price_kopecks=new_price,
    )

    assert previous_price == 100
    assert new_price == 101


@pytest.mark.parametrize(
    ("field_name", "previous_price", "new_price"),
    [
        ("previous_price_kopecks", "100", 101),
        ("new_price_kopecks", 100, "101"),
        ("previous_price_kopecks", True, 101),
        ("new_price_kopecks", 100, False),
        ("previous_price_kopecks", 0, 101),
        ("new_price_kopecks", 100, 0),
        ("previous_price_kopecks", -1, 101),
        ("new_price_kopecks", 100, -1),
    ],
)
def test_invalid_prices_fail_without_writes(
    field_name: str,
    previous_price: object,
    new_price: object,
) -> None:
    session = FakeSession()

    with pytest.raises(ValueError, match=field_name):
        ListingPriceHistoryService(session).record_change(
            listing=_listing(),
            previous_price_kopecks=previous_price,  # type: ignore[arg-type]
            new_price_kopecks=new_price,  # type: ignore[arg-type]
        )

    assert session.added == []
    assert session.flush_calls == 0


def test_missing_listing_identity_fails_without_writes() -> None:
    session = FakeSession()

    with pytest.raises(ValueError, match="listing.*id"):
        ListingPriceHistoryService(session).record_change(
            listing=Listing(),
            previous_price_kopecks=100,
            new_price_kopecks=101,
        )

    assert session.added == []
    assert session.flush_calls == 0


def test_service_does_not_query_or_inspect_other_listings() -> None:
    session = FakeSession()

    result = ListingPriceHistoryService(session).record_change(
        listing=_listing(),
        previous_price_kopecks=100,
        new_price_kopecks=101,
    )

    assert result is not None
    assert not hasattr(session, "get")
    assert not hasattr(session, "scalars")


def test_transaction_is_not_owned_by_service() -> None:
    session = FakeSession()

    ListingPriceHistoryService(session).record_change(
        listing=_listing(),
        previous_price_kopecks=100,
        new_price_kopecks=101,
    )
    ListingPriceHistoryService(session).record_change(
        listing=_listing(),
        previous_price_kopecks=100,
        new_price_kopecks=100,
    )

    assert session.commit_calls == 0
    assert session.rollback_calls == 0
    assert session.close_calls == 0