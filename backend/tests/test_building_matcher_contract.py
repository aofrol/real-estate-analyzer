"""Tests for the framework-independent building matcher contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.matching import BuildingMatchResult, BuildingMatcher
from app.normalization.types import NormalizedListing


def _normalized_listing() -> NormalizedListing:
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
        "source_url": "https://example.invalid/listings/listing-test-001",
        "building_type": "brick",
        "listed_at": datetime(2026, 8, 29),
    }


class ExactTestMatcher(BuildingMatcher):
    """Minimal concrete matcher used to exercise the abstract contract."""

    def match(self, listing: NormalizedListing) -> BuildingMatchResult:
        return BuildingMatchResult(
            matched=True,
            candidate_key="building-test-001",
            confidence=1.0,
            reason="exact_address",
        )


def test_building_matcher_is_abstract() -> None:
    with pytest.raises(TypeError):
        BuildingMatcher()


def test_concrete_matcher_works() -> None:
    result = ExactTestMatcher().match(_normalized_listing())

    assert isinstance(result, BuildingMatchResult)
    assert result.matched is True
    assert result.candidate_key == "building-test-001"


def test_valid_matched_result() -> None:
    result = BuildingMatchResult(
        matched=True,
        candidate_key="building-test-001",
        confidence=1.0,
        reason="exact_address",
    )

    assert result.matched is True
    assert result.candidate_key == "building-test-001"
    assert result.confidence == 1.0
    assert result.reason == "exact_address"


def test_valid_unmatched_result() -> None:
    result = BuildingMatchResult(
        matched=False,
        candidate_key=None,
        confidence=0.0,
        reason="no_candidates",
    )

    assert result.matched is False
    assert result.candidate_key is None
    assert result.confidence == 0.0
    assert result.reason == "no_candidates"


@pytest.mark.parametrize("confidence", [-0.001, -1.0])
def test_confidence_lower_bound(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=confidence,
            reason="no_candidates",
        )


@pytest.mark.parametrize("confidence", [1.001, 2.0])
def test_confidence_upper_bound(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=confidence,
            reason="no_candidates",
        )


def test_matched_requires_candidate_key() -> None:
    with pytest.raises(ValueError, match="candidate_key"):
        BuildingMatchResult(
            matched=True,
            candidate_key=None,
            confidence=1.0,
            reason="exact_address",
        )


@pytest.mark.parametrize("candidate_key", ["", "   "])
def test_matched_rejects_empty_candidate_key(candidate_key: str) -> None:
    with pytest.raises(ValueError, match="candidate_key"):
        BuildingMatchResult(
            matched=True,
            candidate_key=candidate_key,
            confidence=1.0,
            reason="exact_address",
        )


def test_unmatched_forbids_candidate_key() -> None:
    with pytest.raises(ValueError, match="candidate_key"):
        BuildingMatchResult(
            matched=False,
            candidate_key="building-test-001",
            confidence=0.0,
            reason="no_candidates",
        )


@pytest.mark.parametrize("reason", ["", "   "])
def test_reason_is_required(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason=reason,
        )


def test_result_is_immutable() -> None:
    result = BuildingMatchResult(
        matched=True,
        candidate_key="building-test-001",
        confidence=1.0,
        reason="exact_address",
    )

    with pytest.raises(FrozenInstanceError):
        result.confidence = 0.5  # type: ignore[misc]