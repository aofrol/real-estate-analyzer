"""Tests for the framework-independent property matcher contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.matching import PropertyMatchResult, PropertyMatcher
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
        "listed_at": datetime(2026, 8, 29),
    }


class ExactPropertyTestMatcher(PropertyMatcher):
    """Minimal concrete matcher for testing the property contract."""

    def __init__(self) -> None:
        self.received_listing: NormalizedListing | None = None
        self.received_building_key: str | None = None

    def match(
        self,
        *,
        listing: NormalizedListing,
        building_key: str,
    ) -> PropertyMatchResult:
        self.received_listing = listing
        self.received_building_key = building_key
        return PropertyMatchResult(
            matched=True,
            candidate_key="property-test-001",
            confidence=1.0,
            reason="exact_property_identity",
        )


def test_property_matcher_is_abstract() -> None:
    with pytest.raises(TypeError):
        PropertyMatcher()


def test_concrete_test_matcher_works() -> None:
    result = ExactPropertyTestMatcher().match(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert isinstance(result, PropertyMatchResult)
    assert result.matched is True
    assert result.candidate_key == "property-test-001"
    assert result.confidence == 1.0
    assert result.reason == "exact_property_identity"


def test_valid_matched_result() -> None:
    result = PropertyMatchResult(
        matched=True,
        candidate_key="property-test-001",
        confidence=1.0,
        reason="exact_property_identity",
    )

    assert result.matched is True
    assert result.candidate_key == "property-test-001"
    assert result.confidence == 1.0
    assert result.reason == "exact_property_identity"


def test_valid_unmatched_result() -> None:
    result = PropertyMatchResult(
        matched=False,
        candidate_key=None,
        confidence=0.0,
        reason="no_property_candidates",
    )

    assert result.matched is False
    assert result.candidate_key is None
    assert result.confidence == 0.0
    assert result.reason == "no_property_candidates"


@pytest.mark.parametrize("confidence", [-0.1, -1.0])
def test_confidence_below_zero_is_invalid(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=confidence,
            reason="no_property_candidates",
        )


@pytest.mark.parametrize("confidence", [1.1, 2.0])
def test_confidence_above_one_is_invalid(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=confidence,
            reason="no_property_candidates",
        )


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_confidence_is_invalid(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=confidence,
            reason="no_property_candidates",
        )


def test_matched_requires_candidate_key() -> None:
    with pytest.raises(ValueError, match="candidate_key"):
        PropertyMatchResult(
            matched=True,
            candidate_key=None,
            confidence=1.0,
            reason="exact_property_identity",
        )


@pytest.mark.parametrize("candidate_key", ["", "   "])
def test_matched_rejects_empty_candidate_key(candidate_key: str) -> None:
    with pytest.raises(ValueError, match="candidate_key"):
        PropertyMatchResult(
            matched=True,
            candidate_key=candidate_key,
            confidence=1.0,
            reason="exact_property_identity",
        )


def test_unmatched_forbids_candidate_key() -> None:
    with pytest.raises(ValueError, match="candidate_key"):
        PropertyMatchResult(
            matched=False,
            candidate_key="property-test-001",
            confidence=0.0,
            reason="no_property_candidates",
        )


@pytest.mark.parametrize("reason", ["", "   "])
def test_reason_is_required(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason=reason,
        )


def test_result_is_immutable() -> None:
    result = PropertyMatchResult(
        matched=True,
        candidate_key="property-test-001",
        confidence=1.0,
        reason="exact_property_identity",
    )

    with pytest.raises(FrozenInstanceError):
        result.confidence = 0.5  # type: ignore[misc]


def test_building_key_passes_through_unchanged() -> None:
    matcher = ExactPropertyTestMatcher()
    building_key = "application-building-key/001"

    matcher.match(
        listing=_listing(),
        building_key=building_key,
    )

    assert matcher.received_building_key == building_key


def test_same_normalized_listing_object_is_forwarded() -> None:
    matcher = ExactPropertyTestMatcher()
    listing = _listing()

    matcher.match(
        listing=listing,
        building_key="building-test-001",
    )

    assert matcher.received_listing is listing