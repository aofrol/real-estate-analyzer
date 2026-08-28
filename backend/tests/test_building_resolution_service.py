"""Tests for the database-free building resolution service."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.matching import (
    BuildingCandidate,
    BuildingCandidateProvider,
    BuildingMatchResult,
    BuildingMatcher,
    ExactBuildingMatcher,
)
from app.normalization.types import NormalizedListing
from app.resolution import BuildingResolutionResult, BuildingResolutionService


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


class FakeMatcher(BuildingMatcher):
    """Return a configured result and capture matcher calls."""

    def __init__(self, result: BuildingMatchResult) -> None:
        self.result = result
        self.calls = 0
        self.received_listings: list[NormalizedListing] = []

    def match(self, listing: NormalizedListing) -> BuildingMatchResult:
        self.calls += 1
        self.received_listings.append(listing)
        return self.result


def _service(result: BuildingMatchResult) -> tuple[
    BuildingResolutionService,
    FakeMatcher,
]:
    matcher = FakeMatcher(result)
    return BuildingResolutionService(matcher), matcher


def test_matched_resolution() -> None:
    service, _ = _service(
        BuildingMatchResult(
            matched=True,
            candidate_key="building-001",
            confidence=1.0,
            reason="exact_address",
        )
    )

    result = service.resolve(_listing())

    assert result == BuildingResolutionResult(
        status="matched",
        building_key="building-001",
        match_confidence=1.0,
        reason="exact_address",
    )


def test_matched_tiebreak_resolution_preserves_values() -> None:
    service, _ = _service(
        BuildingMatchResult(
            matched=True,
            candidate_key="building-002",
            confidence=0.95,
            reason="exact_address_tiebreak",
        )
    )

    result = service.resolve(_listing())

    assert result == BuildingResolutionResult(
        status="matched",
        building_key="building-002",
        match_confidence=0.95,
        reason="exact_address_tiebreak",
    )


def test_no_candidates_means_create_required() -> None:
    service, _ = _service(
        BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="no_candidates",
        )
    )

    result = service.resolve(_listing())

    assert result == BuildingResolutionResult(
        status="create_required",
        building_key=None,
        match_confidence=0.0,
        reason="no_candidates",
    )


def test_no_exact_address_match_means_create_required() -> None:
    service, _ = _service(
        BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="no_exact_address_match",
        )
    )

    result = service.resolve(_listing())

    assert result.status == "create_required"
    assert result.reason == "no_exact_address_match"
    assert result.building_key is None
    assert result.match_confidence == 0.0


def test_ambiguous_match_stays_ambiguous() -> None:
    service, _ = _service(
        BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="ambiguous_exact_address",
        )
    )

    result = service.resolve(_listing())

    assert result.status == "ambiguous"
    assert result.reason == "ambiguous_exact_address"
    assert result.status != "create_required"


def test_unknown_unmatched_reason_fails_closed() -> None:
    service, _ = _service(
        BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="future_unknown_reason",
        )
    )

    with pytest.raises(ValueError, match="reason"):
        service.resolve(_listing())


def test_matcher_receives_the_same_listing() -> None:
    service, matcher = _service(
        BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="no_candidates",
        )
    )
    listing = _listing()

    service.resolve(listing)

    assert matcher.received_listings == [listing]
    assert matcher.received_listings[0] is listing


def test_matcher_is_called_exactly_once() -> None:
    service, matcher = _service(
        BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="no_candidates",
        )
    )

    service.resolve(_listing())

    assert matcher.calls == 1


def test_resolution_result_is_immutable() -> None:
    result = BuildingResolutionResult(
        status="matched",
        building_key="building-001",
        match_confidence=1.0,
        reason="exact_address",
    )

    with pytest.raises(FrozenInstanceError):
        result.status = "ambiguous"  # type: ignore[misc]


def test_invalid_status() -> None:
    with pytest.raises(ValueError, match="status"):
        BuildingResolutionResult(
            status="created",
            building_key=None,
            match_confidence=0.0,
            reason="no_candidates",
        )


def test_matched_requires_building_key() -> None:
    with pytest.raises(ValueError, match="building_key"):
        BuildingResolutionResult(
            status="matched",
            building_key=None,
            match_confidence=1.0,
            reason="exact_address",
        )


def test_matched_requires_positive_confidence() -> None:
    with pytest.raises(ValueError, match="match_confidence"):
        BuildingResolutionResult(
            status="matched",
            building_key="building-001",
            match_confidence=0.0,
            reason="exact_address",
        )


def test_create_required_forbids_building_key() -> None:
    with pytest.raises(ValueError, match="building_key"):
        BuildingResolutionResult(
            status="create_required",
            building_key="building-001",
            match_confidence=0.0,
            reason="no_candidates",
        )


def test_create_required_requires_zero_confidence() -> None:
    with pytest.raises(ValueError, match="match_confidence"):
        BuildingResolutionResult(
            status="create_required",
            building_key=None,
            match_confidence=0.5,
            reason="no_candidates",
        )


def test_ambiguous_forbids_building_key() -> None:
    with pytest.raises(ValueError, match="building_key"):
        BuildingResolutionResult(
            status="ambiguous",
            building_key="building-001",
            match_confidence=0.0,
            reason="ambiguous_exact_address",
        )


def test_ambiguous_requires_zero_confidence() -> None:
    with pytest.raises(ValueError, match="match_confidence"):
        BuildingResolutionResult(
            status="ambiguous",
            building_key=None,
            match_confidence=0.5,
            reason="ambiguous_exact_address",
        )


@pytest.mark.parametrize("reason", ["", "   "])
def test_reason_must_be_non_empty(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        BuildingResolutionResult(
            status="create_required",
            building_key=None,
            match_confidence=0.0,
            reason=reason,
        )


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf"), float("-inf")])
def test_confidence_must_be_finite_and_in_range(confidence: float) -> None:
    with pytest.raises(ValueError, match="match_confidence"):
        BuildingResolutionResult(
            status="create_required",
            building_key=None,
            match_confidence=confidence,
            reason="no_candidates",
        )


class FakeCandidateProvider(BuildingCandidateProvider):
    """Return one deterministic in-memory candidate."""

    def get_candidates(
        self,
        listing: NormalizedListing,
    ) -> list[BuildingCandidate]:
        return [
            BuildingCandidate(
                key="building-001",
                address_normalized="москва, улица ленина, 1",
                city="Москва",
                latitude=None,
                longitude=None,
                building_type="brick",
                floors_total=10,
            )
        ]


def test_exact_matcher_integration_resolves_existing_building() -> None:
    matcher = ExactBuildingMatcher(FakeCandidateProvider())

    result = BuildingResolutionService(matcher).resolve(_listing())

    assert result.status == "matched"
    assert result.building_key == "building-001"
    assert result.reason == "exact_address"