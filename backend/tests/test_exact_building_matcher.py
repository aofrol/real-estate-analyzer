"""Tests for deterministic exact building matching."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.matching import (
    BuildingCandidate,
    BuildingCandidateProvider,
    BuildingMatchResult,
    ExactBuildingMatcher,
)
from app.normalization.types import NormalizedListing


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
        "listed_at": None,
    }


def _candidate(**overrides: object) -> BuildingCandidate:
    values: dict[str, object] = {
        "key": "building-test-001",
        "address_normalized": "Москва, улица Ленина, 1",
        "city": "Москва",
        "latitude": None,
        "longitude": None,
        "building_type": "brick",
        "floors_total": 10,
    }
    values.update(overrides)
    return BuildingCandidate(**values)  # type: ignore[arg-type]


class FakeCandidateProvider(BuildingCandidateProvider):
    """Return a deterministic in-memory candidate list."""

    def __init__(self, candidates: list[BuildingCandidate]) -> None:
        self.candidates = candidates
        self.received_listings: list[NormalizedListing] = []

    def get_candidates(
        self,
        listing: NormalizedListing,
    ) -> list[BuildingCandidate]:
        self.received_listings.append(listing)
        return self.candidates


def _matcher(
    candidates: list[BuildingCandidate],
) -> ExactBuildingMatcher:
    return ExactBuildingMatcher(FakeCandidateProvider(candidates))


def test_no_candidates() -> None:
    result = _matcher([]).match(_listing())

    assert result == BuildingMatchResult(
        matched=False,
        candidate_key=None,
        confidence=0.0,
        reason="no_candidates",
    )


def test_exact_address_match() -> None:
    result = _matcher([_candidate()]).match(_listing())

    assert result.matched is True
    assert result.candidate_key == "building-test-001"
    assert result.confidence == 1.0
    assert result.reason == "exact_address"


def test_address_case_and_whitespace_are_normalized() -> None:
    listing = _listing()
    listing["address"] = "  Москва,   Улица Ленина, 1 "
    candidate = _candidate(address_normalized="москва, улица ленина, 1")

    result = _matcher([candidate]).match(listing)

    assert result.matched is True
    assert result.confidence == 1.0
    assert result.reason == "exact_address"


def test_no_exact_address_match() -> None:
    result = _matcher(
        [_candidate(address_normalized="Москва, улица Пушкина, 2")]
    ).match(_listing())

    assert result.matched is False
    assert result.candidate_key is None
    assert result.confidence == 0.0
    assert result.reason == "no_exact_address_match"


def test_two_exact_candidates_are_resolved_by_city() -> None:
    candidates = [
        _candidate(key="building-moscow", city="Москва"),
        _candidate(key="building-kazan", city="Казань"),
    ]
    result = _matcher(candidates).match(_listing())

    assert result.matched is True
    assert result.candidate_key == "building-moscow"
    assert result.confidence == 0.95
    assert result.reason == "exact_address_tiebreak"


def test_exact_candidates_are_resolved_by_building_type() -> None:
    listing = _listing()
    listing["city"] = None
    candidates = [
        _candidate(key="building-brick", building_type="brick"),
        _candidate(key="building-panel", building_type="panel"),
    ]

    result = _matcher(candidates).match(listing)

    assert result.matched is True
    assert result.candidate_key == "building-brick"
    assert result.confidence == 0.95
    assert result.reason == "exact_address_tiebreak"


def test_exact_candidates_are_resolved_by_floors_total() -> None:
    listing = _listing()
    listing["city"] = None
    listing["building_type"] = None
    candidates = [
        _candidate(key="building-ten", floors_total=10),
        _candidate(key="building-twelve", floors_total=12),
    ]

    result = _matcher(candidates).match(listing)

    assert result.matched is True
    assert result.candidate_key == "building-ten"
    assert result.confidence == 0.95
    assert result.reason == "exact_address_tiebreak"


def test_equal_exact_address_scores_are_ambiguous() -> None:
    listing = _listing()
    listing["city"] = None
    listing["building_type"] = None
    listing["total_floors"] = None
    candidates = [
        _candidate(key="building-a", city=None, building_type=None, floors_total=None),
        _candidate(key="building-b", city=None, building_type=None, floors_total=None),
    ]

    result = _matcher(candidates).match(listing)

    assert result.matched is False
    assert result.candidate_key is None
    assert result.confidence == 0.0
    assert result.reason == "ambiguous_exact_address"


def test_apartment_fields_do_not_affect_matching() -> None:
    candidate = _candidate()
    baseline = _matcher([candidate]).match(_listing())
    changed_listing = _listing()
    changed_listing.update(
        {
            "rooms": 4,
            "floor": 17,
            "area_sqm": 120.0,
            "asking_price_kopecks": 3_000_000_000,
            "asking_price_per_sqm_kopecks": 25_000_000,
        }
    )

    result = _matcher([candidate]).match(changed_listing)

    assert result == baseline


def test_coordinates_do_not_affect_matching() -> None:
    candidate = _candidate(latitude=10.0, longitude=20.0)
    changed_candidate = _candidate(latitude=-10.0, longitude=-20.0)

    first = _matcher([candidate]).match(_listing())
    second = _matcher([changed_candidate]).match(_listing())

    assert first == second
    assert first.reason == "exact_address"


@pytest.mark.parametrize("address", [None, "", "   "])
def test_invalid_listing_address(address: object) -> None:
    listing = _listing()
    listing["address"] = address  # type: ignore[assignment]

    with pytest.raises(ValueError, match="address"):
        _matcher([]).match(listing)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"key": ""}, "key"),
        ({"address_normalized": "   "}, "address_normalized"),
        ({"latitude": 55.75, "longitude": None}, "latitude"),
        ({"latitude": None, "longitude": 37.62}, "longitude"),
        ({"latitude": 90.1, "longitude": 37.62}, "latitude"),
        ({"latitude": 55.75, "longitude": 180.1}, "longitude"),
        ({"floors_total": 0}, "floors_total"),
        ({"floors_total": -1}, "floors_total"),
    ],
)
def test_candidate_invariants(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _candidate(**overrides)


def test_candidate_is_immutable() -> None:
    candidate = _candidate()

    with pytest.raises(FrozenInstanceError):
        candidate.key = "other-key"  # type: ignore[misc]


def test_candidate_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        BuildingCandidateProvider()