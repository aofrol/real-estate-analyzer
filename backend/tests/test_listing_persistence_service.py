"""Database-free tests for ListingPersistenceService."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.models.listing import Listing
from app.models.property import Property
from app.models.source import Source
from app.normalization.types import NormalizedListing
from app.persistence import ListingPersistenceService


def _listing(
    *,
    external_id: str = "listing-test-001",
    source_url: str | None = "https://example.test/listing-test-001",
    listed_at: datetime | None = datetime(2026, 8, 29),
    asking_price_kopecks: int = 1_250_000_000,
    asking_price_per_sqm_kopecks: int = 22_522_523,
) -> NormalizedListing:
    return {
        "external_id": external_id,
        "address": "Москва, улица Ленина, 1",
        "area_sqm": 55.5,
        "rooms": 2,
        "is_studio": False,
        "floor": 5,
        "total_floors": 10,
        "asking_price_kopecks": asking_price_kopecks,
        "asking_price_per_sqm_kopecks": asking_price_per_sqm_kopecks,
        "city": "Москва",
        "latitude": 55.75,
        "longitude": 37.62,
        "source_url": source_url,
        "building_type": "brick",
        "listed_at": listed_at,
    }


def _source(source_id: UUID) -> Source:
    return Source(
        id=source_id,
        name="Test source",
        adapter_class="app.sources.mock.MockAdapter",
    )


def _property(property_id: UUID) -> Property:
    return Property(
        id=property_id,
        building_id=uuid4(),
        floor=5,
        rooms=2,
        area_total=55.5,
        is_studio=False,
    )


class _ScalarResult:
    def __init__(self, listing: Listing | None) -> None:
        self._listing = listing

    def one_or_none(self) -> Listing | None:
        return self._listing


class FakeSession:
    """Record ORM operations without opening a database connection."""

    def __init__(
        self,
        *,
        source: Source | None,
        property_row: Property | None,
        existing_listing: Listing | None = None,
    ) -> None:
        self.source = source
        self.property_row = property_row
        self.existing_listing = existing_listing
        self.get_calls: list[tuple[type[object], UUID]] = []
        self.statements: list[object] = []
        self.added: list[Listing] = []
        self.flush_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def get(self, model: type[object], key: UUID):
        self.get_calls.append((model, key))
        if model is Source:
            return self.source
        if model is Property:
            return self.property_row
        return None

    def scalars(self, statement: object) -> _ScalarResult:
        self.statements.append(statement)
        return _ScalarResult(self.existing_listing)

    def add(self, listing_row: Listing) -> None:
        self.added.append(listing_row)

    def flush(self) -> None:
        self.flush_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1


def _service(
    *,
    source_id: UUID | None = None,
    property_row: Property | None = None,
    existing_listing: Listing | None = None,
) -> tuple[ListingPersistenceService, FakeSession, UUID, Property]:
    source_id = source_id or uuid4()
    property_row = property_row or _property(uuid4())
    session = FakeSession(
        source=_source(source_id),
        property_row=property_row,
        existing_listing=existing_listing,
    )
    return (
        ListingPersistenceService(session),
        session,
        source_id,
        property_row,
    )


def test_create_maps_identity_and_canonical_money_values() -> None:
    service, session, source_id, property_row = _service()
    listing = _listing()

    result = service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=listing,
    )

    assert result is session.added[0]
    assert result.source_id == source_id
    assert result.property_id == property_row.id
    assert result.external_id == listing["external_id"]
    assert result.asking_price == listing["asking_price_kopecks"]
    assert result.asking_price_per_sqm == listing["asking_price_per_sqm_kopecks"]
    assert result.url == listing["source_url"]
    assert result.listed_at == listing["listed_at"]
    assert result.duplicate_of_id is None


def test_create_loads_source_and_property_with_session_get() -> None:
    service, session, source_id, property_row = _service()

    service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=_listing(),
    )

    assert session.get_calls == [
        (Source, source_id),
        (Property, property_row.id),
    ]


def test_create_adds_and_flushes_once_without_transaction_ownership() -> None:
    service, session, source_id, property_row = _service()

    service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=_listing(),
    )

    assert len(session.added) == 1
    assert session.flush_calls == 1
    assert session.commit_calls == 0
    assert session.rollback_calls == 0
    assert session.close_calls == 0


def test_reuse_returns_exact_existing_object_and_preserves_identity() -> None:
    source_id = uuid4()
    property_row = _property(uuid4())
    listing_id = uuid4()
    existing = Listing(
        id=listing_id,
        source_id=source_id,
        property_id=property_row.id,
        external_id="listing-test-001",
        url="https://old.example/listing",
        asking_price=1_250_000_000,
        asking_price_per_sqm=22_522_523,
        listed_at=datetime(2026, 8, 20),
    )
    service, session, _, _ = _service(
        source_id=source_id,
        property_row=property_row,
        existing_listing=existing,
    )

    result = service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=_listing(
            source_url="https://new.example/listing",
            listed_at=datetime(2026, 8, 29),
        ),
    )

    assert result is existing
    assert result.id == listing_id
    assert session.added == []
    assert session.flush_calls == 1


def test_reuse_updates_only_supported_mutable_fields() -> None:
    source_id = uuid4()
    property_row = _property(uuid4())
    existing = Listing(
        id=uuid4(),
        source_id=source_id,
        property_id=property_row.id,
        external_id="listing-test-001",
        url="https://old.example/listing",
        asking_price=1,
        asking_price_per_sqm=2,
        status="sold",
        listed_at=datetime(2026, 8, 20),
        removed_at=datetime(2026, 8, 28),
        duplicate_of_id=uuid4(),
        extra={"keep": True},
    )
    before_identity = (
        existing.id,
        existing.source_id,
        existing.property_id,
        existing.external_id,
    )
    service, session, _, _ = _service(
        source_id=source_id,
        property_row=property_row,
        existing_listing=existing,
    )

    service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=_listing(
            asking_price_kopecks=3,
            asking_price_per_sqm_kopecks=4,
            source_url="https://new.example/listing",
            listed_at=datetime(2026, 8, 29),
        ),
    )

    assert (
        existing.id,
        existing.source_id,
        existing.property_id,
        existing.external_id,
    ) == before_identity
    assert existing.asking_price == 3
    assert existing.asking_price_per_sqm == 4
    assert existing.url == "https://new.example/listing"
    assert existing.status == "sold"
    assert existing.listed_at == datetime(2026, 8, 20)
    assert existing.removed_at == datetime(2026, 8, 28)
    assert existing.duplicate_of_id is not None
    assert existing.extra == {"keep": True}
    assert session.added == []
    assert session.flush_calls == 1


def test_reuse_does_not_flush_when_mutable_state_is_unchanged() -> None:
    source_id = uuid4()
    property_row = _property(uuid4())
    existing = Listing(
        id=uuid4(),
        source_id=source_id,
        property_id=property_row.id,
        external_id="listing-test-001",
        url="https://example.test/listing-test-001",
        asking_price=1_250_000_000,
        asking_price_per_sqm=22_522_523,
        listed_at=datetime(2026, 8, 29),
    )
    service, session, _, _ = _service(
        source_id=source_id,
        property_row=property_row,
        existing_listing=existing,
    )

    result = service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=_listing(),
    )

    assert result is existing
    assert session.flush_calls == 0


def test_reuse_does_not_erase_url_or_listed_at_when_input_is_missing() -> None:
    source_id = uuid4()
    property_row = _property(uuid4())
    original_listed_at = datetime(2026, 8, 20)
    existing = Listing(
        id=uuid4(),
        source_id=source_id,
        property_id=property_row.id,
        external_id="listing-test-001",
        url="https://example.test/known",
        asking_price=1_250_000_000,
        asking_price_per_sqm=22_522_523,
        listed_at=original_listed_at,
    )
    service, session, _, _ = _service(
        source_id=source_id,
        property_row=property_row,
        existing_listing=existing,
    )

    service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=_listing(source_url=None, listed_at=None),
    )

    assert existing.url == "https://example.test/known"
    assert existing.listed_at == original_listed_at
    assert session.flush_calls == 0


def test_reuse_fills_missing_listed_at_but_never_changes_known_value() -> None:
    source_id = uuid4()
    property_row = _property(uuid4())
    existing = Listing(
        id=uuid4(),
        source_id=source_id,
        property_id=property_row.id,
        external_id="listing-test-001",
        url=None,
        asking_price=1_250_000_000,
        asking_price_per_sqm=22_522_523,
        listed_at=None,
    )
    service, session, _, _ = _service(
        source_id=source_id,
        property_row=property_row,
        existing_listing=existing,
    )

    service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=_listing(listed_at=datetime(2026, 8, 29)),
    )

    assert existing.listed_at == datetime(2026, 8, 29)
    assert session.flush_calls == 1


def test_property_conflict_fails_without_mutating_existing_listing() -> None:
    source_id = uuid4()
    expected_property = _property(uuid4())
    existing = Listing(
        id=uuid4(),
        source_id=source_id,
        property_id=uuid4(),
        external_id="listing-test-001",
        url="https://old.example/listing",
        asking_price=1,
        asking_price_per_sqm=2,
        duplicate_of_id=uuid4(),
    )
    before = deepcopy(
        {
            "property_id": existing.property_id,
            "url": existing.url,
            "asking_price": existing.asking_price,
            "asking_price_per_sqm": existing.asking_price_per_sqm,
            "duplicate_of_id": existing.duplicate_of_id,
        }
    )
    service, session, _, _ = _service(
        source_id=source_id,
        property_row=expected_property,
        existing_listing=existing,
    )

    with pytest.raises(
        ValueError,
        match=(
            rf"Listing property conflict for source_key={source_id}, "
            rf"property_key={expected_property.id}, "
            r"external_id=listing-test-001"
        ),
    ):
        service.persist(
            source_key=str(source_id),
            property_key=str(expected_property.id),
            listing=_listing(),
        )

    assert {
        "property_id": existing.property_id,
        "url": existing.url,
        "asking_price": existing.asking_price,
        "asking_price_per_sqm": existing.asking_price_per_sqm,
        "duplicate_of_id": existing.duplicate_of_id,
    } == before
    assert session.added == []
    assert session.flush_calls == 0


@pytest.mark.parametrize(
    ("source_key", "property_key", "field_name"),
    [
        ("", str(uuid4()), "source_key"),
        ("   ", str(uuid4()), "source_key"),
        ("not-a-uuid", str(uuid4()), "source_key"),
        (str(uuid4()), "", "property_key"),
        (str(uuid4()), "   ", "property_key"),
        (str(uuid4()), "not-a-uuid", "property_key"),
    ],
)
def test_invalid_uuid_keys_fail_before_any_session_lookup(
    source_key: str,
    property_key: str,
    field_name: str,
) -> None:
    service, session, _, _ = _service()

    with pytest.raises(ValueError, match=field_name):
        service.persist(
            source_key=source_key,
            property_key=property_key,
            listing=_listing(),
        )

    assert session.get_calls == []
    assert session.statements == []
    assert session.added == []
    assert session.flush_calls == 0


def test_invalid_external_id_fails_before_any_session_lookup() -> None:
    service, session, source_id, property_row = _service()

    with pytest.raises(ValueError, match="external_id"):
        service.persist(
            source_key=str(source_id),
            property_key=str(property_row.id),
            listing=_listing(external_id="   "),
        )

    assert session.get_calls == []
    assert session.statements == []
    assert session.added == []
    assert session.flush_calls == 0


def test_external_id_is_stored_without_mutation() -> None:
    service, session, source_id, property_row = _service()
    listing = _listing(external_id="  source-native-id  ")

    service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=listing,
    )

    assert session.added[0].external_id == "  source-native-id  "
    assert listing["external_id"] == "  source-native-id  "


def test_missing_source_fails_without_property_lookup_or_writes() -> None:
    source_id = uuid4()
    property_row = _property(uuid4())
    session = FakeSession(source=None, property_row=property_row)

    with pytest.raises(ValueError, match="Source"):
        ListingPersistenceService(session).persist(
            source_key=str(source_id),
            property_key=str(property_row.id),
            listing=_listing(),
        )

    assert session.get_calls == [(Source, source_id)]
    assert session.statements == []
    assert session.added == []
    assert session.flush_calls == 0


def test_missing_property_fails_without_listing_lookup_or_writes() -> None:
    source_id = uuid4()
    property_id = uuid4()
    session = FakeSession(source=_source(source_id), property_row=None)

    with pytest.raises(ValueError, match="Property"):
        ListingPersistenceService(session).persist(
            source_key=str(source_id),
            property_key=str(property_id),
            listing=_listing(),
        )

    assert session.get_calls == [
        (Source, source_id),
        (Property, property_id),
    ]
    assert session.statements == []
    assert session.added == []
    assert session.flush_calls == 0


def test_listing_lookup_is_composed_from_only_source_and_external_identity() -> None:
    service, session, source_id, property_row = _service()

    service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=_listing(),
    )

    assert len(session.statements) == 1
    statement = session.statements[0]
    sql = str(
        statement.whereclause.compile(compile_kwargs={"literal_binds": True})
    )
    assert "listings.source_id =" in sql
    assert "listings.external_id =" in sql
    assert "listings.property_id" not in sql


def test_listing_input_is_not_mutated() -> None:
    service, _, source_id, property_row = _service()
    listing = _listing()
    before = deepcopy(listing)

    service.persist(
        source_key=str(source_id),
        property_key=str(property_row.id),
        listing=listing,
    )

    assert listing == before