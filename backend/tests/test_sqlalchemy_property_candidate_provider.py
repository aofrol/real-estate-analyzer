"""Database-free tests for the SQLAlchemy Property candidate provider."""

from __future__ import annotations

import copy
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.sql import operators

from app.matching import (
    ConservativePropertyMatcher,
    PropertyCandidate,
    SQLAlchemyPropertyCandidateProvider,
)
from app.models.property import Property


def _listing() -> dict:
    return {
        "external_id": "listing-test-001",
        "address": "Москва, улица Ленина, 1",
        "area_sqm": 55.5,
        "rooms": 2,
        "is_studio": False,
        "floor": 5,
        "total_floors": 10,
        "asking_price_kopecks": 1_250_000_000,
        "asking_price_per_sqm_kopecks": 22_522_523,
        "city": "Москва",
        "latitude": None,
        "longitude": None,
        "source_url": None,
        "building_type": "brick",
        "listed_at": None,
    }


def _property(
    *,
    property_id: uuid.UUID,
    building_id: uuid.UUID,
    floor: int | None = 5,
    rooms: int = 2,
    area_total: Decimal = Decimal("55.50"),
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


class FakeScalarResult:
    def __init__(self, rows: list[Property]) -> None:
        self.rows = rows

    def all(self) -> list[Property]:
        return self.rows


class FakeSession:
    """Capture SQL statements and return configured ORM rows."""

    def __init__(self, rows: list[Property]) -> None:
        self.rows = rows
        self.statements = []
        self.add_calls = 0
        self.delete_calls = 0
        self.flush_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def scalars(self, statement):
        self.statements.append(statement)
        return FakeScalarResult(self.rows)

    def add(self, _value) -> None:
        self.add_calls += 1

    def delete(self, _value) -> None:
        self.delete_calls += 1

    def flush(self) -> None:
        self.flush_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1


def _where_values(statement) -> dict[str, object]:
    return {
        criterion.left.key: criterion.right.value
        for criterion in statement._where_criteria
    }


@pytest.mark.parametrize("building_key", ["", "   ", "not-a-uuid"])
def test_invalid_building_key_is_rejected_without_query(
    building_key: str,
) -> None:
    session = FakeSession([])

    with pytest.raises(ValueError, match="building_key"):
        SQLAlchemyPropertyCandidateProvider(session).get_candidates(
            listing=_listing(),
            building_key=building_key,
        )

    assert session.statements == []


def test_valid_uuid_with_no_property_rows_returns_empty_list() -> None:
    session = FakeSession([])

    candidates = SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(uuid.uuid4()),
    )

    assert candidates == []
    assert len(session.statements) == 1


def test_one_property_maps_to_candidate() -> None:
    building_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    property_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    property_row = _property(
        property_id=property_id,
        building_id=building_id,
    )
    session = FakeSession([property_row])

    candidates = SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(building_id),
    )

    assert candidates == [
        PropertyCandidate(
            key=str(property_id),
            floor=5,
            rooms=2,
            is_studio=False,
            area_sqm=55.5,
        )
    ]


def test_multiple_properties_map_correctly() -> None:
    building_id = uuid.UUID("00000000-0000-0000-0000-000000000003")
    first = _property(
        property_id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
        building_id=building_id,
        floor=1,
        rooms=1,
        area_total=Decimal("31.20"),
        is_studio=False,
    )
    second = _property(
        property_id=uuid.UUID("00000000-0000-0000-0000-000000000005"),
        building_id=building_id,
        floor=None,
        rooms=0,
        area_total=Decimal("24.00"),
        is_studio=True,
    )
    session = FakeSession([first, second])

    candidates = SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(building_id),
    )

    assert candidates == [
        PropertyCandidate(
            key=str(first.id),
            floor=1,
            rooms=1,
            is_studio=False,
            area_sqm=31.2,
        ),
        PropertyCandidate(
            key=str(second.id),
            floor=None,
            rooms=0,
            is_studio=True,
            area_sqm=24.0,
        ),
    ]


def test_nullable_floor_is_preserved() -> None:
    building_id = uuid.uuid4()
    property_row = _property(
        property_id=uuid.uuid4(),
        building_id=building_id,
        floor=None,
    )
    session = FakeSession([property_row])

    candidates = SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(building_id),
    )

    assert candidates[0].floor is None


def test_rooms_value_is_preserved_exactly() -> None:
    building_id = uuid.uuid4()
    property_row = _property(
        property_id=uuid.uuid4(),
        building_id=building_id,
        rooms=0,
        is_studio=True,
    )
    session = FakeSession([property_row])

    candidates = SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(building_id),
    )

    assert candidates[0].rooms == 0


def test_is_studio_value_is_preserved_exactly() -> None:
    building_id = uuid.uuid4()
    property_row = _property(
        property_id=uuid.uuid4(),
        building_id=building_id,
        rooms=0,
        is_studio=True,
    )
    session = FakeSession([property_row])

    candidates = SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(building_id),
    )

    assert candidates[0].is_studio is True


def test_decimal_area_converts_to_float_without_provider_rounding() -> None:
    building_id = uuid.uuid4()
    property_row = _property(
        property_id=uuid.uuid4(),
        building_id=building_id,
        area_total=Decimal("55.505"),
    )
    session = FakeSession([property_row])

    candidates = SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(building_id),
    )

    assert candidates[0].area_sqm == 55.505
    assert isinstance(candidates[0].area_sqm, float)


def test_property_id_converts_to_string() -> None:
    building_id = uuid.uuid4()
    property_id = uuid.uuid4()
    session = FakeSession(
        [
            _property(
                property_id=property_id,
                building_id=building_id,
            )
        ]
    )

    candidates = SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(building_id),
    )

    assert candidates[0].key == str(property_id)
    assert isinstance(candidates[0].key, str)


def test_query_uses_provided_building_uuid() -> None:
    building_id = uuid.UUID("00000000-0000-0000-0000-000000000006")
    session = FakeSession([])

    SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(building_id),
    )

    assert _where_values(session.statements[0]) == {
        "building_id": building_id,
    }


def test_query_does_not_use_listing_descriptive_attributes() -> None:
    building_id = uuid.uuid4()
    property_row = _property(
        property_id=uuid.uuid4(),
        building_id=building_id,
        floor=1,
        rooms=1,
        area_total=Decimal("31.20"),
        is_studio=False,
    )
    listing = _listing()
    listing["floor"] = 99
    listing["rooms"] = 9
    listing["area_sqm"] = 999.99
    listing["is_studio"] = True
    session = FakeSession([property_row])

    candidates = SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=listing,
        building_key=str(building_id),
    )

    assert len(candidates) == 1
    assert candidates[0].key == str(property_row.id)


def test_listing_is_not_mutated() -> None:
    building_id = uuid.uuid4()
    session = FakeSession([])
    listing = _listing()
    before = copy.deepcopy(listing)

    SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=listing,
        building_key=str(building_id),
    )

    assert listing == before


def test_session_is_queried_exactly_once() -> None:
    session = FakeSession([])

    SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(uuid.uuid4()),
    )

    assert len(session.statements) == 1


def test_query_orders_by_property_id_ascending() -> None:
    session = FakeSession([])

    SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(uuid.uuid4()),
    )

    order_by = session.statements[0]._order_by_clauses
    assert len(order_by) == 1
    assert order_by[0].element.key == "id"
    assert order_by[0].modifier is operators.asc_op


def test_provider_performs_no_write_or_transaction_operations() -> None:
    session = FakeSession([])

    SQLAlchemyPropertyCandidateProvider(session).get_candidates(
        listing=_listing(),
        building_key=str(uuid.uuid4()),
    )

    assert session.add_calls == 0
    assert session.delete_calls == 0
    assert session.flush_calls == 0
    assert session.commit_calls == 0
    assert session.rollback_calls == 0
    assert session.close_calls == 0


def test_provider_integrates_with_conservative_matcher() -> None:
    building_id = uuid.uuid4()
    property_row = _property(
        property_id=uuid.uuid4(),
        building_id=building_id,
        floor=5,
        rooms=2,
        area_total=Decimal("55.50"),
        is_studio=False,
    )
    provider = SQLAlchemyPropertyCandidateProvider(FakeSession([property_row]))

    result = ConservativePropertyMatcher(provider).match(
        listing=_listing(),
        building_key=str(building_id),
    )

    assert result.matched is True
    assert result.candidate_key == str(property_row.id)
    assert result.confidence == 0.80
    assert result.reason == "exact_descriptive_signature"