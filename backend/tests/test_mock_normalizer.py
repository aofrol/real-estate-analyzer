"""Tests for the deterministic MockNormalizer implementation."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.normalization import MockNormalizer, NormalizedListing
from app.sources.mock import MockAdapter


def _mock_raw_listing() -> dict:
    listings = MockAdapter().collect()
    assert listings
    return listings[0]


def test_mock_adapter_payload_normalizes_to_canonical_listing() -> None:
    """Real MockAdapter data maps to every canonical field."""
    raw_listing = _mock_raw_listing()
    original_raw_listing = deepcopy(raw_listing)

    normalized = MockNormalizer().normalize(raw_listing)

    assert isinstance(normalized, dict)
    assert set(normalized) == set(NormalizedListing.__annotations__)
    assert normalized["external_id"] == "mock-001"
    assert normalized["address"] == "г. Москва, ул. Ленина, д. 1"
    assert normalized["city"] == "Москва"
    assert normalized["area_sqm"] == 55.5
    assert normalized["rooms"] == 2
    assert normalized["is_studio"] is False
    assert normalized["floor"] == 5
    assert normalized["total_floors"] is None
    assert normalized["asking_price_kopecks"] == 1_250_000_000
    assert normalized["asking_price_per_sqm_kopecks"] == 22_522_523
    assert isinstance(normalized["asking_price_kopecks"], int)
    assert isinstance(normalized["asking_price_per_sqm_kopecks"], int)
    assert normalized["area_sqm"] > 0
    assert normalized["latitude"] is None
    assert normalized["longitude"] is None
    assert normalized["source_url"] == "https://example.invalid/listings/mock-001"
    assert normalized["building_type"] is None
    assert normalized["listed_at"] is None
    assert not {
        "source_id",
        "building_id",
        "property_id",
        "listing_id",
        "duplicate_of_id",
    }.intersection(normalized)
    assert raw_listing == original_raw_listing


def test_mock_normalizer_rejects_missing_external_id() -> None:
    raw_listing = _mock_raw_listing()
    raw_listing.pop("external_id")

    with pytest.raises(ValueError, match="external_id"):
        MockNormalizer().normalize(raw_listing)


def test_mock_normalizer_rejects_empty_external_id() -> None:
    raw_listing = _mock_raw_listing()
    raw_listing["external_id"] = ""

    with pytest.raises(ValueError, match="external_id"):
        MockNormalizer().normalize(raw_listing)


def test_mock_normalizer_rejects_missing_address() -> None:
    raw_listing = _mock_raw_listing()
    raw_listing.pop("address")

    with pytest.raises(ValueError, match="address"):
        MockNormalizer().normalize(raw_listing)


def test_mock_normalizer_rejects_empty_address() -> None:
    raw_listing = _mock_raw_listing()
    raw_listing["address"] = ""

    with pytest.raises(ValueError, match="address"):
        MockNormalizer().normalize(raw_listing)


@pytest.mark.parametrize("area", [0, -1])
def test_mock_normalizer_rejects_non_positive_area(area: int) -> None:
    raw_listing = _mock_raw_listing()
    raw_listing["area"] = area

    with pytest.raises(ValueError, match="area"):
        MockNormalizer().normalize(raw_listing)


@pytest.mark.parametrize("price", [0, -1])
def test_mock_normalizer_rejects_non_positive_price(price: int) -> None:
    raw_listing = _mock_raw_listing()
    raw_listing["price"] = price

    with pytest.raises(ValueError, match="price"):
        MockNormalizer().normalize(raw_listing)