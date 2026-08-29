"""Database-free tests for PropertyResolutionService."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.matching.property import PropertyMatchResult, PropertyMatcher
from app.normalization.types import NormalizedListing
from app.resolution import PropertyResolutionResult, PropertyResolutionService


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


class FakePropertyMatcher(PropertyMatcher):
    """Return a configured result and capture matcher calls."""

    def __init__(self, result: PropertyMatchResult) -> None:
        self.result = result
        self.calls = 0
        self.received_listing: NormalizedListing | None = None
        self.received_building_key: str | None = None

    def match(
        self,
        *,
        listing: NormalizedListing,
        building_key: str,
    ) -> PropertyMatchResult:
        self.calls += 1
        self.received_listing = listing
        self.received_building_key = building_key
        return self.result


def _service(
    result: PropertyMatchResult,
) -> tuple[PropertyResolutionService, FakePropertyMatcher]:
    matcher = FakePropertyMatcher(result)
    return PropertyResolutionService(matcher), matcher


def test_matched_result_is_resolved() -> None:
    service, _ = _service(
        PropertyMatchResult(
            matched=True,
            candidate_key="property-test-001",
            confidence=0.80,
            reason="exact_descriptive_signature",
        )
    )

    result = service.resolve(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert result == PropertyResolutionResult(
        status="matched",
        property_key="property-test-001",
        match_confidence=0.80,
        reason="exact_descriptive_signature",
    )


@pytest.mark.parametrize(
    "reason",
    ["no_property_candidates", "no_exact_property_signature"],
)
def test_create_required_reasons_map_to_create_required(reason: str) -> None:
    service, _ = _service(
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason=reason,
        )
    )

    result = service.resolve(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert result == PropertyResolutionResult(
        status="create_required",
        property_key=None,
        match_confidence=0.0,
        reason=reason,
    )


def test_ambiguous_reason_maps_to_ambiguous() -> None:
    service, _ = _service(
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="ambiguous_property_candidates",
        )
    )

    result = service.resolve(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert result == PropertyResolutionResult(
        status="ambiguous",
        property_key=None,
        match_confidence=0.0,
        reason="ambiguous_property_candidates",
    )


def test_ambiguous_never_becomes_create_required() -> None:
    service, _ = _service(
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="ambiguous_property_candidates",
        )
    )

    result = service.resolve(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert result.status == "ambiguous"
    assert result.status != "create_required"


def test_unknown_unmatched_reason_fails_closed() -> None:
    service, _ = _service(
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="unexpected_reason",
        )
    )

    with pytest.raises(ValueError, match="Unsupported matcher reason"):
        service.resolve(
            listing=_listing(),
            building_key="building-test-001",
        )


def test_matcher_is_called_exactly_once() -> None:
    service, matcher = _service(
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="no_property_candidates",
        )
    )

    service.resolve(
        listing=_listing(),
        building_key="building-test-001",
    )

    assert matcher.calls == 1


def test_exact_same_listing_object_is_forwarded() -> None:
    service, matcher = _service(
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="no_property_candidates",
        )
    )
    listing = _listing()

    service.resolve(
        listing=listing,
        building_key="building-test-001",
    )

    assert matcher.received_listing is listing


def test_exact_building_key_is_forwarded() -> None:
    service, matcher = _service(
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="no_property_candidates",
        )
    )
    building_key = "application-building-key/001"

    service.resolve(
        listing=_listing(),
        building_key=building_key,
    )

    assert matcher.received_building_key == building_key


def test_resolution_does_not_mutate_listing() -> None:
    service, _ = _service(
        PropertyMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="no_property_candidates",
        )
    )
    listing = _listing()
    before = deepcopy(listing)

    service.resolve(
        listing=listing,
        building_key="building-test-001",
    )

    assert listing == before


def test_valid_matched_resolution_result() -> None:
    result = PropertyResolutionResult(
        status="matched",
        property_key="property-test-001",
        match_confidence=0.80,
        reason="exact_descriptive_signature",
    )

    assert result.status == "matched"
    assert result.property_key == "property-test-001"
    assert result.match_confidence == 0.80
    assert result.reason == "exact_descriptive_signature"


def test_valid_create_required_resolution_result() -> None:
    result = PropertyResolutionResult(
        status="create_required",
        property_key=None,
        match_confidence=0.0,
        reason="no_property_candidates",
    )

    assert result.status == "create_required"
    assert result.property_key is None
    assert result.match_confidence == 0.0


def test_valid_ambiguous_resolution_result() -> None:
    result = PropertyResolutionResult(
        status="ambiguous",
        property_key=None,
        match_confidence=0.0,
        reason="ambiguous_property_candidates",
    )

    assert result.status == "ambiguous"
    assert result.property_key is None
    assert result.match_confidence == 0.0


def test_invalid_status() -> None:
    with pytest.raises(ValueError, match="status"):
        PropertyResolutionResult(
            status="unknown",
            property_key=None,
            match_confidence=0.0,
            reason="no_property_candidates",
        )


@pytest.mark.parametrize(
    "confidence",
    [
        -0.1,
        1.1,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
    ],
)
def test_invalid_match_confidence(confidence: object) -> None:
    with pytest.raises(ValueError, match="match_confidence"):
        PropertyResolutionResult(
            status="create_required",
            property_key=None,
            match_confidence=confidence,  # type: ignore[arg-type]
            reason="no_property_candidates",
        )


def test_matched_requires_property_key() -> None:
    with pytest.raises(ValueError, match="property_key"):
        PropertyResolutionResult(
            status="matched",
            property_key=None,
            match_confidence=0.80,
            reason="exact_descriptive_signature",
        )


@pytest.mark.parametrize("property_key", ["", "   "])
def test_matched_rejects_blank_property_key(property_key: str) -> None:
    with pytest.raises(ValueError, match="property_key"):
        PropertyResolutionResult(
            status="matched",
            property_key=property_key,
            match_confidence=0.80,
            reason="exact_descriptive_signature",
        )


def test_matched_requires_positive_confidence() -> None:
    with pytest.raises(ValueError, match="match_confidence"):
        PropertyResolutionResult(
            status="matched",
            property_key="property-test-001",
            match_confidence=0.0,
            reason="exact_descriptive_signature",
        )


@pytest.mark.parametrize("status", ["create_required", "ambiguous"])
def test_unresolved_status_requires_no_property_key(status: str) -> None:
    with pytest.raises(ValueError, match="property_key"):
        PropertyResolutionResult(
            status=status,
            property_key="property-test-001",
            match_confidence=0.0,
            reason="no_property_candidates",
        )


@pytest.mark.parametrize("status", ["create_required", "ambiguous"])
def test_unresolved_status_requires_zero_confidence(status: str) -> None:
    with pytest.raises(ValueError, match="match_confidence"):
        PropertyResolutionResult(
            status=status,
            property_key=None,
            match_confidence=0.5,
            reason="no_property_candidates",
        )


@pytest.mark.parametrize("reason", ["", "   "])
def test_reason_is_required(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        PropertyResolutionResult(
            status="create_required",
            property_key=None,
            match_confidence=0.0,
            reason=reason,
        )


def test_resolution_result_is_immutable() -> None:
    result = PropertyResolutionResult(
        status="matched",
        property_key="property-test-001",
        match_confidence=0.80,
        reason="exact_descriptive_signature",
    )

    with pytest.raises(FrozenInstanceError):
        result.status = "ambiguous"  # type: ignore[misc]