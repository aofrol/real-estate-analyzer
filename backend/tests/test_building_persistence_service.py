"""Database-free tests for BuildingPersistenceService."""

from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.models.building import Building
from app.normalization.types import NormalizedListing
from app.persistence import BuildingPersistenceResult, BuildingPersistenceService
from app.resolution import BuildingResolutionResult


def _listing() -> NormalizedListing:
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
        "latitude": 55.75,
        "longitude": 37.62,
        "source_url": None,
        "building_type": "brick",
        "listed_at": datetime(2026, 8, 29),
    }


def _matched_resolution(building_key: str) -> BuildingResolutionResult:
    return BuildingResolutionResult(
        status="matched",
        building_key=building_key,
        match_confidence=1.0,
        reason="exact_address",
    )


def _create_required_resolution() -> BuildingResolutionResult:
    return BuildingResolutionResult(
        status="create_required",
        building_key=None,
        match_confidence=0.0,
        reason="no_candidates",
    )


def _ambiguous_resolution() -> BuildingResolutionResult:
    return BuildingResolutionResult(
        status="ambiguous",
        building_key=None,
        match_confidence=0.0,
        reason="ambiguous_exact_address",
    )


class FakeSession:
    """Track session operations without opening a database connection."""

    def __init__(
        self,
        *,
        existing_building: Building | None = None,
        flushed_id: uuid.UUID | None = None,
    ) -> None:
        self.existing_building = existing_building
        self.flushed_id = flushed_id
        self.get_calls: list[tuple[type[Building], object]] = []
        self.added: list[Building] = []
        self.flush_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def get(self, model: type[Building], key: object) -> Building | None:
        self.get_calls.append((model, key))
        return self.existing_building

    def add(self, building: Building) -> None:
        self.added.append(building)

    def flush(self) -> None:
        self.flush_calls += 1
        if self.added and self.flushed_id is not None:
            self.added[-1].id = self.flushed_id

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_matched_existing_building_is_reused_without_creation() -> None:
    building_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    building = Building(
        id=building_id,
        address_raw="Москва, улица Ленина, 1",
    )
    session = FakeSession(existing_building=building)
    service = BuildingPersistenceService(session)

    result = service.persist(
        listing=_listing(),
        resolution=_matched_resolution(str(building_id)),
    )

    assert result == BuildingPersistenceResult(
        building_key=str(building_id),
        created=False,
    )
    assert session.get_calls == [(Building, building_id)]
    assert session.added == []
    assert session.flush_calls == 0
    assert session.commit_calls == 0


def test_matched_building_key_is_parsed_as_uuid() -> None:
    building_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    session = FakeSession(
        existing_building=Building(
            id=building_id,
            address_raw="Москва, улица Ленина, 1",
        )
    )

    BuildingPersistenceService(session).persist(
        listing=_listing(),
        resolution=_matched_resolution(str(building_id)),
    )

    assert session.get_calls[0][0] is Building
    assert session.get_calls[0][1] == building_id
    assert isinstance(session.get_calls[0][1], uuid.UUID)


def test_malformed_matched_building_key_fails_without_creation() -> None:
    session = FakeSession()

    with pytest.raises(ValueError, match="building_key"):
        BuildingPersistenceService(session).persist(
            listing=_listing(),
            resolution=_matched_resolution("not-a-uuid"),
        )

    assert session.get_calls == []
    assert session.added == []
    assert session.flush_calls == 0


def test_matched_building_missing_from_persistence_fails_without_creation() -> None:
    building_id = uuid.UUID("00000000-0000-0000-0000-000000000003")
    session = FakeSession()

    with pytest.raises(ValueError, match="building_key"):
        BuildingPersistenceService(session).persist(
            listing=_listing(),
            resolution=_matched_resolution(str(building_id)),
        )

    assert session.get_calls == [(Building, building_id)]
    assert session.added == []
    assert session.flush_calls == 0


def test_create_required_creates_building_with_derived_fields() -> None:
    created_id = uuid.UUID("00000000-0000-0000-0000-000000000004")
    session = FakeSession(flushed_id=created_id)
    listing = _listing()

    result = BuildingPersistenceService(session).persist(
        listing=listing,
        resolution=_create_required_resolution(),
    )

    assert len(session.added) == 1
    building = session.added[0]
    assert building.address_raw == listing["address"]
    assert building.address_normalized == "москва, улица ленина, 1"
    assert building.city == "Москва"
    assert building.floors_total == 10
    assert building.building_type == "brick"
    assert result == BuildingPersistenceResult(
        building_key=str(created_id),
        created=True,
    )


def test_create_required_canonicalizes_address() -> None:
    session = FakeSession(
        flushed_id=uuid.UUID("00000000-0000-0000-0000-000000000005")
    )
    listing = _listing()
    listing["address"] = "  Москва,   Улица Ленина, 1  "

    BuildingPersistenceService(session).persist(
        listing=listing,
        resolution=_create_required_resolution(),
    )

    assert session.added[0].address_raw == "  Москва,   Улица Ленина, 1  "
    assert session.added[0].address_normalized == "москва, улица ленина, 1"


def test_create_required_leaves_unsupported_fields_unset() -> None:
    session = FakeSession(
        flushed_id=uuid.UUID("00000000-0000-0000-0000-000000000006")
    )

    BuildingPersistenceService(session).persist(
        listing=_listing(),
        resolution=_create_required_resolution(),
    )

    building = session.added[0]
    assert building.district is None
    assert building.street is None
    assert building.house_number is None
    assert building.postal_code is None
    assert building.year_built is None
    assert building.location is None


def test_create_required_adds_and_flushes_once_without_commit() -> None:
    session = FakeSession(
        flushed_id=uuid.UUID("00000000-0000-0000-0000-000000000007")
    )

    BuildingPersistenceService(session).persist(
        listing=_listing(),
        resolution=_create_required_resolution(),
    )

    assert len(session.added) == 1
    assert session.flush_calls == 1
    assert session.commit_calls == 0


def test_ambiguous_resolution_refuses_persistence() -> None:
    session = FakeSession()

    with pytest.raises(ValueError, match="ambiguous"):
        BuildingPersistenceService(session).persist(
            listing=_listing(),
            resolution=_ambiguous_resolution(),
        )

    assert session.get_calls == []
    assert session.added == []
    assert session.flush_calls == 0
    assert session.commit_calls == 0


def test_persistence_result_is_immutable() -> None:
    result = BuildingPersistenceResult(
        building_key="building-001",
        created=True,
    )

    with pytest.raises(FrozenInstanceError):
        result.created = False  # type: ignore[misc]


@pytest.mark.parametrize("building_key", ["", "   "])
def test_persistence_result_requires_building_key(building_key: str) -> None:
    with pytest.raises(ValueError, match="building_key"):
        BuildingPersistenceResult(
            building_key=building_key,
            created=False,
        )


def test_persistence_result_requires_bool_created() -> None:
    with pytest.raises(ValueError, match="created"):
        BuildingPersistenceResult(
            building_key="building-001",
            created=1,  # type: ignore[arg-type]
        )


def test_no_transaction_ownership_on_matched_and_create_paths() -> None:
    building_id = uuid.UUID("00000000-0000-0000-0000-000000000008")
    matched_session = FakeSession(
        existing_building=Building(
            id=building_id,
            address_raw="Москва, улица Ленина, 1",
        )
    )
    create_session = FakeSession(flushed_id=building_id)

    BuildingPersistenceService(matched_session).persist(
        listing=_listing(),
        resolution=_matched_resolution(str(building_id)),
    )
    BuildingPersistenceService(create_session).persist(
        listing=_listing(),
        resolution=_create_required_resolution(),
    )

    assert matched_session.commit_calls == 0
    assert matched_session.rollback_calls == 0
    assert create_session.commit_calls == 0
    assert create_session.rollback_calls == 0