"""Database-free tests for conservative property matching."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.matching import (
    ConservativePropertyMatcher,
    PropertyCandidate,
    PropertyCandidateProvider,
)
from app.normalization.types import NormalizedListing


def _listing(**overrides: object) -> NormalizedListing:
    listing: NormalizedListing = {
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
    listing.update(overrides)  # type: ignore[arg-type]
    return listing


def _candidate(**overrides: object) -> PropertyCandidate:
    values: dict[str, object] = {
        "key": "property-test-001",
        "floor": 5,
        "rooms": 2,
        "is_studio": False,
        "area_sqm": 55.5,
    }
    values.update(overrides)
    return PropertyCandidate(**values)  # type: ignore[arg-type]


class FakePropertyCandidateProvider(PropertyCandidateProvider):
    """In-memory provider that records matcher inputs and call count."""

    def __init__(self, candidates: list[PropertyCandidate]) -> None:
        self.candidates = candidates
        self.received_listing: NormalizedListing | None = None
        self.received_building_key: str | None = None
        self.call_count = 0

    def get_candidates(
        self,
        *,
        listing: NormalizedListing,
        building_key: str,
    ) -> list[PropertyCandidate]:
        self.call_count += 1
        self.received_listing = listing
        self.received_building_key = building_key
        return self.candidates


def _matcher(
    candidates: list[PropertyCandidate],
) -> tuple[ConservativePropertyMatcher, FakePropertyCandidateProvider]:
    provider = FakePropertyCandidateProvider(candidates)
    return ConservativePropertyMatcher(provider), provider


def test_no_candidates_returns_unmatched_result() -> None:
    matcher, _ = _matcher([])

    result = matcher.match(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert result.matched is False
    assert result.candidate_key is None
    assert result.confidence == 0.0
    assert result.reason == "no_property_candidates"


def test_one_exact_descriptive_signature_matches() -> None:
    matcher, _ = _matcher([_candidate()])

    result = matcher.match(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert result.matched is True
    assert result.candidate_key == "property-test-001"
    assert result.confidence == 0.80
    assert result.reason == "exact_descriptive_signature"


def test_area_55_5_equals_55_50() -> None:
    matcher, _ = _matcher([_candidate(area_sqm=55.50)])

    result = matcher.match(
        listing=_listing(area_sqm=55.5),
        building_key="building-test-001",
    )

    assert result.matched is True


@pytest.mark.parametrize(
    ("listing_area", "candidate_area"),
    [(55.504, 55.50), (55.505, 55.51)],
)
def test_area_uses_round_half_up(
    listing_area: float,
    candidate_area: float,
) -> None:
    matcher, _ = _matcher([_candidate(area_sqm=candidate_area)])

    result = matcher.match(
        listing=_listing(area_sqm=listing_area),
        building_key="building-test-001",
    )

    assert result.matched is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"floor": 6},
        {"rooms": 3},
        {"is_studio": True},
        {"area_sqm": 55.51},
    ],
)
def test_different_signature_attribute_does_not_match(
    overrides: dict[str, object],
) -> None:
    matcher, _ = _matcher([_candidate(**overrides)])

    result = matcher.match(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert result.matched is False
    assert result.candidate_key is None
    assert result.confidence == 0.0
    assert result.reason == "no_exact_property_signature"


def test_candidates_exist_but_none_match_returns_no_exact_signature() -> None:
    matcher, _ = _matcher([_candidate(floor=6), _candidate(rooms=3)])

    result = matcher.match(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert result.matched is False
    assert result.candidate_key is None
    assert result.confidence == 0.0
    assert result.reason == "no_exact_property_signature"


def test_two_exact_candidates_are_ambiguous() -> None:
    matcher, _ = _matcher(
        [
            _candidate(key="property-test-001"),
            _candidate(key="property-test-002"),
        ]
    )

    result = matcher.match(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert result.matched is False
    assert result.candidate_key is None
    assert result.confidence == 0.0
    assert result.reason == "ambiguous_property_candidates"


def test_candidate_order_cannot_resolve_ambiguity() -> None:
    first_matcher, _ = _matcher(
        [
            _candidate(key="property-test-001"),
            _candidate(key="property-test-002"),
        ]
    )
    second_matcher, _ = _matcher(
        [
            _candidate(key="property-test-002"),
            _candidate(key="property-test-001"),
        ]
    )

    first_result = first_matcher.match(
        listing=_listing(),
        building_key="building-test-001",
    )
    second_result = second_matcher.match(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert first_result.reason == "ambiguous_property_candidates"
    assert second_result.reason == "ambiguous_property_candidates"
    assert first_result.candidate_key is None
    assert second_result.candidate_key is None


def test_building_key_is_passed_unchanged() -> None:
    matcher, provider = _matcher([])
    building_key = "application-building-key/001"

    matcher.match(
        listing=_listing(),
        building_key=building_key,
    )

    assert provider.received_building_key == building_key


def test_listing_object_is_forwarded_unchanged() -> None:
    matcher, provider = _matcher([])
    listing = _listing()

    matcher.match(
        listing=listing,
        building_key="building-test-001",
    )

    assert provider.received_listing is listing


def test_provider_called_exactly_once() -> None:
    matcher, provider = _matcher([_candidate()])

    matcher.match(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert provider.call_count == 1


@pytest.mark.parametrize("building_key", ["", "   "])
def test_invalid_building_key_fails_before_provider_call(
    building_key: str,
) -> None:
    matcher, provider = _matcher([_candidate()])

    with pytest.raises(ValueError, match="building_key"):
        matcher.match(
            listing=_listing(),
            building_key=building_key,
        )

    assert provider.call_count == 0


def test_studio_with_nullable_rooms_matches_same_candidate_signature() -> None:
    matcher, _ = _matcher(
        [
            _candidate(
                rooms=None,
                is_studio=True,
            )
        ]
    )

    result = matcher.match(
        listing=_listing(
            rooms=None,
            is_studio=True,
        ),
        building_key="building-test-001",
    )

    assert result.matched is True


def test_studio_rooms_are_not_coerced() -> None:
    matcher, _ = _matcher(
        [
            _candidate(
                rooms=0,
                is_studio=True,
            )
        ]
    )

    result = matcher.match(
        listing=_listing(
            rooms=None,
            is_studio=True,
        ),
        building_key="building-test-001",
    )

    assert result.matched is False
    assert result.reason == "no_exact_property_signature"


def test_property_candidate_is_immutable() -> None:
    candidate = _candidate()

    with pytest.raises(FrozenInstanceError):
        candidate.area_sqm = 60.0  # type: ignore[misc]


def test_property_candidate_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        PropertyCandidateProvider()


@pytest.mark.parametrize("key", ["", "   "])
def test_property_candidate_rejects_invalid_key(key: str) -> None:
    with pytest.raises(ValueError, match="key"):
        _candidate(key=key)


def test_property_candidate_accepts_nullable_floor() -> None:
    candidate = _candidate(floor=None)

    assert candidate.floor is None


def test_property_candidate_rejects_invalid_floor_type() -> None:
    with pytest.raises(ValueError, match="floor"):
        _candidate(floor="5")


def test_property_candidate_accepts_nullable_rooms() -> None:
    candidate = _candidate(rooms=None)

    assert candidate.rooms is None


def test_property_candidate_rejects_negative_rooms() -> None:
    with pytest.raises(ValueError, match="rooms"):
        _candidate(rooms=-1)


def test_property_candidate_rejects_invalid_rooms_type() -> None:
    with pytest.raises(ValueError, match="rooms"):
        _candidate(rooms="2")


def test_property_candidate_rejects_invalid_is_studio_type() -> None:
    with pytest.raises(ValueError, match="is_studio"):
        _candidate(is_studio=1)


@pytest.mark.parametrize("area_sqm", [0, -1])
def test_property_candidate_rejects_non_positive_area(area_sqm: int) -> None:
    with pytest.raises(ValueError, match="area_sqm"):
        _candidate(area_sqm=area_sqm)


@pytest.mark.parametrize(
    "area_sqm",
    [float("nan"), float("inf"), float("-inf")],
)
def test_property_candidate_rejects_non_finite_area(area_sqm: float) -> None:
    with pytest.raises(ValueError, match="area_sqm"):
        _candidate(area_sqm=area_sqm)


def test_property_candidate_does_not_enforce_studio_rooms_relationship() -> None:
    nullable_rooms = _candidate(rooms=None, is_studio=True)
    zero_rooms = _candidate(rooms=0, is_studio=True)

    assert nullable_rooms.rooms is None
    assert zero_rooms.rooms == 0