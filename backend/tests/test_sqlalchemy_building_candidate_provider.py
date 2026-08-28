"""Database-free tests for the SQLAlchemy building candidate provider."""

from __future__ import annotations

import uuid

import pytest

from app.matching import (
    BuildingCandidate,
    ExactBuildingMatcher,
    SQLAlchemyBuildingCandidateProvider,
    canonicalize_address,
)
from app.models.building import Building


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


def _building(
    *,
    building_id: uuid.UUID | None = None,
    address_normalized: str = "москва, улица ленина, 1",
    city: str | None = "Москва",
    building_type: str | None = "brick",
    floors_total: int | None = 10,
) -> Building:
    return Building(
        id=building_id or uuid.uuid4(),
        address_raw=address_normalized,
        address_normalized=address_normalized,
        city=city,
        building_type=building_type,
        floors_total=floors_total,
    )


class FakeScalarResult:
    def __init__(self, rows: list[Building]) -> None:
        self.rows = rows

    def all(self) -> list[Building]:
        return self.rows


class FakeSession:
    """Capture SQL statements and return configured ORM rows."""

    def __init__(self, rows: list[Building]) -> None:
        self.rows = rows
        self.statements = []
        self.commit_calls = 0
        self.flush_calls = 0
        self.rollback_calls = 0

    def scalars(self, statement):
        self.statements.append(statement)
        return FakeScalarResult(self.rows)

    def commit(self) -> None:
        self.commit_calls += 1

    def flush(self) -> None:
        self.flush_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def _where_values(statement) -> dict[str, object]:
    return {
        criterion.left.key: criterion.right.value
        for criterion in statement._where_criteria
    }


def test_address_canonicalization() -> None:
    assert canonicalize_address("  Москва,   Улица Ленина, 1  ") == (
        "москва, улица ленина, 1"
    )


@pytest.mark.parametrize("address", ["", "   "])
def test_invalid_address_canonicalization(address: str) -> None:
    with pytest.raises(ValueError, match="address"):
        canonicalize_address(address)


def test_provider_maps_building_to_candidate() -> None:
    building_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    building = _building(building_id=building_id)
    session = FakeSession([building])

    candidates = SQLAlchemyBuildingCandidateProvider(session).get_candidates(
        _listing()
    )

    assert candidates == [
        BuildingCandidate(
            key=str(building_id),
            address_normalized="москва, улица ленина, 1",
            city="Москва",
            latitude=None,
            longitude=None,
            building_type="brick",
            floors_total=10,
        )
    ]


def test_provider_returns_multiple_rows_in_database_result_order() -> None:
    first = _building(
        building_id=uuid.UUID("00000000-0000-0000-0000-000000000001")
    )
    second = _building(
        building_id=uuid.UUID("00000000-0000-0000-0000-000000000002")
    )
    session = FakeSession([first, second])

    candidates = SQLAlchemyBuildingCandidateProvider(session).get_candidates(
        _listing()
    )

    assert [candidate.key for candidate in candidates] == [
        str(first.id),
        str(second.id),
    ]
    order_by = session.statements[0]._order_by_clauses
    assert len(order_by) == 1
    assert order_by[0].element.key == "id"


def test_provider_returns_empty_result() -> None:
    session = FakeSession([])

    assert SQLAlchemyBuildingCandidateProvider(session).get_candidates(
        _listing()
    ) == []


def test_session_is_injected() -> None:
    session = FakeSession([])
    provider = SQLAlchemyBuildingCandidateProvider(session)

    provider.get_candidates(_listing())

    assert provider._session is session
    assert len(session.statements) == 1


def test_provider_has_no_persistence_side_effects() -> None:
    session = FakeSession([])

    SQLAlchemyBuildingCandidateProvider(session).get_candidates(_listing())

    assert session.commit_calls == 0
    assert session.flush_calls == 0
    assert session.rollback_calls == 0


def test_query_uses_address_and_city_when_city_is_present() -> None:
    session = FakeSession([])
    listing = _listing()
    listing["address"] = "  Москва,   Улица Ленина, 1 "

    SQLAlchemyBuildingCandidateProvider(session).get_candidates(listing)

    assert _where_values(session.statements[0]) == {
        "address_normalized": "москва, улица ленина, 1",
        "city": "Москва",
    }


def test_query_uses_only_address_when_city_is_none() -> None:
    session = FakeSession([])
    listing = _listing()
    listing["city"] = None

    SQLAlchemyBuildingCandidateProvider(session).get_candidates(listing)

    assert _where_values(session.statements[0]) == {
        "address_normalized": "москва, улица ленина, 1",
    }


def test_provider_integrates_with_exact_matcher() -> None:
    building = _building(
        building_id=uuid.UUID("00000000-0000-0000-0000-000000000001")
    )
    provider = SQLAlchemyBuildingCandidateProvider(FakeSession([building]))

    result = ExactBuildingMatcher(provider).match(_listing())

    assert result.matched is True
    assert result.candidate_key == str(building.id)
    assert result.reason == "exact_address"