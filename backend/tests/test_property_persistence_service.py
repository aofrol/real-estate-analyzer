"""Database-free tests for PropertyPersistenceService."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.models.building import Building
from app.models.property import Property
from app.normalization.types import NormalizedListing
from app.persistence import PropertyPersistenceService
from app.resolution import PropertyResolutionResult


def _listing(
    *,
    rooms: int = 2,
    is_studio: bool = False,
    floor: int | None = 5,
    area_sqm: float = 55.5,
) -> NormalizedListing:
    return {
        "external_id": "listing-test-001",
        "address": "Москва, улица Ленина, 1",
        "area_sqm": area_sqm,
        "rooms": rooms,
        "is_studio": is_studio,
        "floor": floor,
        "total_floors": 10,
        "asking_price_kopecks": 1_250_000_000,
        "asking_price_per_sqm_kopecks": 22_522_523,
        "city": "Москва",
        "latitude": 55.75,
        "longitude": 37.62,
        "source_url": None,
        "building_type": "brick",
        "listed_at": datetime(2026, 8, 29),
    }


def _building(building_id: UUID) -> Building:
    return Building(
        id=building_id,
        address_raw="Москва, улица Ленина, 1",
    )


def _property(
    *,
    property_id: UUID,
    building_id: UUID,
    floor: int | None = 3,
    rooms: int = 1,
    area_total: Decimal = Decimal("40.00"),
    is_studio: bool = False,
) -> Property:
    return Property(
        id=property_id,
        building_id=building_id,
        floor=floor,
        rooms=rooms,
        area_total=area_total,
        is_studio=is_studio,
    )


def _matched_resolution(property_key: str) -> PropertyResolutionResult:
    return PropertyResolutionResult(
        status="matched",
        property_key=property_key,
        match_confidence=0.80,
        reason="exact_descriptive_signature",
    )


def _create_required_resolution() -> PropertyResolutionResult:
    return PropertyResolutionResult(
        status="create_required",
        property_key=None,
        match_confidence=0.0,
        reason="no_property_candidates",
    )


def _ambiguous_resolution() -> PropertyResolutionResult:
    return PropertyResolutionResult(
        status="ambiguous",
        property_key=None,
        match_confidence=0.0,
        reason="ambiguous_property_candidates",
    )


class FakeSession:
    """Record ORM operations without opening a database connection."""

    def __init__(
        self,
        *,
        buildings: dict[UUID, Building] | None = None,
        properties: dict[UUID, Property] | None = None,
    ) -> None:
        self.buildings = buildings or {}
        self.properties = properties or {}
        self.get_calls: list[tuple[type[object], UUID]] = []
        self.added: list[Property] = []
        self.flush_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def get(self, model: type[object], key: UUID):
        self.get_calls.append((model, key))
        if model is Building:
            return self.buildings.get(key)
        if model is Property:
            return self.properties.get(key)
        return None

    def add(self, property_row: Property) -> None:
        self.added.append(property_row)

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
    building_id: UUID,
    property_row: Property | None = None,
) -> tuple[PropertyPersistenceService, FakeSession]:
    session = FakeSession(
        buildings={building_id: _building(building_id)},
        properties=(
            {property_row.id: property_row}
            if property_row is not None
            else {}
        ),
    )
    return PropertyPersistenceService(session), session


def test_matched_returns_existing_property() -> None:
    building_id = uuid4()
    property_id = uuid4()
    property_row = _property(
        property_id=property_id,
        building_id=building_id,
    )
    service, session = _service(
        building_id=building_id,
        property_row=property_row,
    )

    result = service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=_matched_resolution(str(property_id)),
    )

    assert result is property_row
    assert session.get_calls == [
        (Building, building_id),
        (Property, property_id),
    ]


def test_matched_performs_no_add_or_flush() -> None:
    building_id = uuid4()
    property_id = uuid4()
    service, session = _service(
        building_id=building_id,
        property_row=_property(
            property_id=property_id,
            building_id=building_id,
        ),
    )

    service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=_matched_resolution(str(property_id)),
    )

    assert session.added == []
    assert session.flush_calls == 0


def test_matched_does_not_mutate_existing_property() -> None:
    building_id = uuid4()
    property_id = uuid4()
    property_row = _property(
        property_id=property_id,
        building_id=building_id,
    )
    before = {
        "building_id": property_row.building_id,
        "floor": property_row.floor,
        "rooms": property_row.rooms,
        "area_total": property_row.area_total,
        "is_studio": property_row.is_studio,
    }
    service, _ = _service(
        building_id=building_id,
        property_row=property_row,
    )

    service.persist(
        listing=_listing(
            floor=5,
            rooms=2,
            area_sqm=55.5,
        ),
        building_key=str(building_id),
        resolution=_matched_resolution(str(property_id)),
    )

    assert {
        "building_id": property_row.building_id,
        "floor": property_row.floor,
        "rooms": property_row.rooms,
        "area_total": property_row.area_total,
        "is_studio": property_row.is_studio,
    } == before


def test_matched_invalid_property_key_is_rejected() -> None:
    building_id = uuid4()
    service, session = _service(building_id=building_id)

    with pytest.raises(ValueError, match="property_key"):
        service.persist(
            listing=_listing(),
            building_key=str(building_id),
            resolution=_matched_resolution("not-a-uuid"),
        )

    assert session.added == []
    assert session.flush_calls == 0


def test_matched_missing_property_is_rejected() -> None:
    building_id = uuid4()
    property_id = uuid4()
    service, session = _service(building_id=building_id)

    with pytest.raises(ValueError, match="property_key"):
        service.persist(
            listing=_listing(),
            building_key=str(building_id),
            resolution=_matched_resolution(str(property_id)),
        )

    assert session.added == []
    assert session.flush_calls == 0


def test_matched_property_from_another_building_is_rejected() -> None:
    building_id = uuid4()
    another_building_id = uuid4()
    property_id = uuid4()
    service, session = _service(
        building_id=building_id,
        property_row=_property(
            property_id=property_id,
            building_id=another_building_id,
        ),
    )

    with pytest.raises(ValueError, match="property_key.*building_key"):
        service.persist(
            listing=_listing(),
            building_key=str(building_id),
            resolution=_matched_resolution(str(property_id)),
        )

    assert session.added == []
    assert session.flush_calls == 0


def test_matched_does_not_overwrite_fields_from_listing() -> None:
    building_id = uuid4()
    property_id = uuid4()
    property_row = _property(
        property_id=property_id,
        building_id=building_id,
        floor=3,
        rooms=1,
        area_total=Decimal("40.00"),
    )
    service, _ = _service(
        building_id=building_id,
        property_row=property_row,
    )

    service.persist(
        listing=_listing(
            floor=5,
            rooms=2,
            area_sqm=55.5,
        ),
        building_key=str(building_id),
        resolution=_matched_resolution(str(property_id)),
    )

    assert property_row.floor == 3
    assert property_row.rooms == 1
    assert property_row.area_total == Decimal("40.00")


def test_create_required_creates_one_property_with_canonical_mapping() -> None:
    building_id = uuid4()
    listing = _listing()
    service, session = _service(building_id=building_id)

    result = service.persist(
        listing=listing,
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert len(session.added) == 1
    assert result is session.added[0]
    assert result.building_id == building_id
    assert result.floor == listing["floor"]
    assert result.rooms == listing["rooms"]
    assert result.area_total == listing["area_sqm"]
    assert result.is_studio == listing["is_studio"]
    assert result.area_living is None
    assert result.area_kitchen is None


def test_create_required_adds_exactly_once() -> None:
    building_id = uuid4()
    service, session = _service(building_id=building_id)

    service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert len(session.added) == 1


def test_create_required_flushes_exactly_once() -> None:
    building_id = uuid4()
    service, session = _service(building_id=building_id)

    service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert session.flush_calls == 1


def test_create_required_returns_created_property() -> None:
    building_id = uuid4()
    service, session = _service(building_id=building_id)

    result = service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert result is session.added[0]


def test_create_required_preserves_nullable_floor() -> None:
    building_id = uuid4()
    service, session = _service(building_id=building_id)

    result = service.persist(
        listing=_listing(floor=None),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert result.floor is None


def test_create_required_preserves_canonical_studio_values() -> None:
    building_id = uuid4()
    service, _ = _service(building_id=building_id)

    result = service.persist(
        listing=_listing(
            rooms=0,
            is_studio=True,
            area_sqm=27.4,
            floor=8,
        ),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert result.rooms == 0
    assert result.is_studio is True


def test_create_required_preserves_non_studio_rooms() -> None:
    building_id = uuid4()
    service, _ = _service(building_id=building_id)

    result = service.persist(
        listing=_listing(
            rooms=3,
            is_studio=False,
        ),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert result.rooms == 3
    assert result.is_studio is False


def test_create_required_maps_area_directly_from_area_sqm() -> None:
    building_id = uuid4()
    service, _ = _service(building_id=building_id)

    result = service.persist(
        listing=_listing(area_sqm=55.505),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert result.area_total == 55.505


@pytest.mark.parametrize("building_key", ["", "   ", "not-a-uuid"])
def test_invalid_building_key_is_rejected_without_session_query(
    building_key: str,
) -> None:
    service, session = _service(building_id=uuid4())

    with pytest.raises(ValueError, match="building_key"):
        service.persist(
            listing=_listing(),
            building_key=building_key,
            resolution=_create_required_resolution(),
        )

    assert session.get_calls == []
    assert session.added == []
    assert session.flush_calls == 0


def test_valid_building_key_looks_up_building() -> None:
    building_id = uuid4()
    service, session = _service(building_id=building_id)

    service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert session.get_calls[0] == (Building, building_id)


def test_missing_building_is_rejected_without_writes() -> None:
    building_id = uuid4()
    session = FakeSession()
    service = PropertyPersistenceService(session)

    with pytest.raises(ValueError, match="building_key"):
        service.persist(
            listing=_listing(),
            building_key=str(building_id),
            resolution=_create_required_resolution(),
        )

    assert session.added == []
    assert session.flush_calls == 0


def test_create_required_does_not_query_property() -> None:
    building_id = uuid4()
    service, session = _service(building_id=building_id)

    service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert all(model is not Property for model, _ in session.get_calls)


def test_ambiguous_resolution_is_rejected_without_writes() -> None:
    building_id = uuid4()
    service, session = _service(building_id=building_id)

    with pytest.raises(ValueError, match="ambiguous"):
        service.persist(
            listing=_listing(),
            building_key=str(building_id),
            resolution=_ambiguous_resolution(),
        )

    assert session.added == []
    assert session.flush_calls == 0


def test_ambiguous_resolution_never_creates_property() -> None:
    building_id = uuid4()
    service, session = _service(building_id=building_id)

    with pytest.raises(ValueError, match="ambiguous"):
        service.persist(
            listing=_listing(),
            building_key=str(building_id),
            resolution=_ambiguous_resolution(),
        )

    assert session.added == []


def test_listing_is_not_mutated() -> None:
    building_id = uuid4()
    service, _ = _service(building_id=building_id)
    listing = _listing()
    before = deepcopy(listing)

    service.persist(
        listing=listing,
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )

    assert listing == before


def test_resolution_is_not_modified() -> None:
    building_id = uuid4()
    service, _ = _service(building_id=building_id)
    resolution = _create_required_resolution()

    service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=resolution,
    )

    assert resolution == _create_required_resolution()


def test_transaction_is_not_owned_by_service() -> None:
    building_id = uuid4()
    matched_property_id = uuid4()
    matched_service, matched_session = _service(
        building_id=building_id,
        property_row=_property(
            property_id=matched_property_id,
            building_id=building_id,
        ),
    )
    create_service, create_session = _service(building_id=building_id)
    ambiguous_service, ambiguous_session = _service(building_id=building_id)

    matched_service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=_matched_resolution(str(matched_property_id)),
    )
    create_service.persist(
        listing=_listing(),
        building_key=str(building_id),
        resolution=_create_required_resolution(),
    )
    with pytest.raises(ValueError, match="ambiguous"):
        ambiguous_service.persist(
            listing=_listing(),
            building_key=str(building_id),
            resolution=_ambiguous_resolution(),
        )

    for session in (matched_session, create_session, ambiguous_session):
        assert session.commit_calls == 0
        assert session.rollback_calls == 0
        assert session.close_calls == 0