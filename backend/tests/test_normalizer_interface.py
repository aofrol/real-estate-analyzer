"""Tests for the framework-independent normalizer interface."""

from __future__ import annotations

from typing import Any

from app.normalization import NormalizedListing, Normalizer


class ConcreteNormalizer(Normalizer):
    """Minimal test implementation of the normalizer contract."""

    def normalize(self, raw_listing: dict[str, Any]) -> NormalizedListing:
        return dict(raw_listing)


def test_normalizer_is_abstract() -> None:
    """The interface itself cannot be instantiated."""
    try:
        Normalizer()
    except TypeError:
        pass
    else:
        raise AssertionError("Normalizer must remain abstract")


def test_concrete_normalizer_returns_canonical_normalized_listing() -> None:
    """A concrete implementation can return a complete normalized listing."""
    normalizer = ConcreteNormalizer()
    raw_listing: NormalizedListing = {
        "external_id": "raw-001",
        "address": "Москва, улица Ленина, 1",
        "city": "Москва",
        "area_sqm": 55.5,
        "rooms": 2,
        "is_studio": False,
        "floor": 5,
        "total_floors": 10,
        "asking_price_kopecks": 1_250_000_000,
        "asking_price_per_sqm_kopecks": 22_522_522,
        "latitude": None,
        "longitude": None,
        "source_url": None,
        "building_type": None,
        "listed_at": None,
    }

    normalized = normalizer.normalize(raw_listing)

    assert isinstance(normalized, dict)
    assert normalized == raw_listing
    assert normalized is not raw_listing
    assert normalized["external_id"] == "raw-001"
    assert normalized["address"] == "Москва, улица Ленина, 1"
    assert normalized["area_sqm"] == 55.5
    assert normalized["rooms"] == 2
    assert normalized["is_studio"] is False
    assert normalized["asking_price_kopecks"] == 1_250_000_000
    assert normalized["asking_price_per_sqm_kopecks"] == 22_522_522

    database_identifiers = {
        "source_id",
        "building_id",
        "property_id",
        "listing_id",
        "duplicate_of_id",
    }
    assert not database_identifiers.intersection(normalized)