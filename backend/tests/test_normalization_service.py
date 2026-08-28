"""Tests for the framework-independent normalization service boundary."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from app.normalization import (
    MockNormalizer,
    NormalizationService,
    NormalizedListing,
    Normalizer,
)
from app.sources.mock import MockAdapter


class FakeNormalizer(Normalizer):
    """Capture normalized input and return a known canonical result."""

    def __init__(self, result: NormalizedListing) -> None:
        self.received: list[dict[str, Any]] = []
        self.result = result

    def normalize(self, raw_listing: dict[str, Any]) -> NormalizedListing:
        self.received.append(raw_listing)
        return self.result


def _normalized_result() -> NormalizedListing:
    return {
        "external_id": "normalized-001",
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
        "building_type": None,
        "listed_at": None,
    }


def test_service_passes_raw_data_to_normalizer() -> None:
    fake = FakeNormalizer(_normalized_result())
    raw_data = {
        "title": "Квартира",
        "address": "Москва, улица Ленина, 1",
        "area": 55.5,
        "price": 12_500_000,
    }

    NormalizationService(fake).normalize_raw_listing(
        external_id="mock-001",
        raw_data=raw_data,
    )

    assert fake.received == [
        {
            "title": "Квартира",
            "address": "Москва, улица Ленина, 1",
            "area": 55.5,
            "price": 12_500_000,
            "external_id": "mock-001",
        }
    ]


def test_persisted_external_id_is_authoritative() -> None:
    fake = FakeNormalizer(_normalized_result())
    raw_data = {"external_id": "payload-999", "address": "Москва"}

    NormalizationService(fake).normalize_raw_listing(
        external_id="persisted-001",
        raw_data=raw_data,
    )

    assert fake.received[0]["external_id"] == "persisted-001"


def test_raw_data_is_not_mutated() -> None:
    fake = FakeNormalizer(_normalized_result())
    raw_data = {
        "external_id": "payload-999",
        "details": {"area": 55.5},
    }
    original_raw_data = deepcopy(raw_data)

    NormalizationService(fake).normalize_raw_listing(
        external_id="persisted-001",
        raw_data=raw_data,
    )

    assert raw_data == original_raw_data
    assert fake.received[0] is not raw_data


def test_service_does_not_add_database_identifiers() -> None:
    fake = FakeNormalizer(_normalized_result())
    raw_data = {"address": "Москва, улица Ленина, 1"}

    NormalizationService(fake).normalize_raw_listing(
        external_id="persisted-001",
        raw_data=raw_data,
    )

    database_identifiers = {
        "source_id",
        "building_id",
        "property_id",
        "listing_id",
        "duplicate_of_id",
    }
    assert not database_identifiers.intersection(fake.received[0])


def test_service_returns_normalizer_result_unchanged() -> None:
    result = _normalized_result()
    fake = FakeNormalizer(result)

    returned = NormalizationService(fake).normalize_raw_listing(
        external_id="persisted-001",
        raw_data={"address": "Москва"},
    )

    assert returned is result


@pytest.mark.parametrize("external_id", ["", "   ", 123])
def test_service_rejects_invalid_external_id(external_id: object) -> None:
    fake = FakeNormalizer(_normalized_result())

    with pytest.raises(ValueError, match="external_id"):
        NormalizationService(fake).normalize_raw_listing(
            external_id=external_id,  # type: ignore[arg-type]
            raw_data={},
        )


@pytest.mark.parametrize("raw_data", [None, [], "raw payload"])
def test_service_rejects_invalid_raw_data(raw_data: object) -> None:
    fake = FakeNormalizer(_normalized_result())

    with pytest.raises(ValueError, match="raw_data"):
        NormalizationService(fake).normalize_raw_listing(
            external_id="persisted-001",
            raw_data=raw_data,  # type: ignore[arg-type]
        )


def test_service_with_mock_normalizer_uses_mock_adapter_payload() -> None:
    raw_listing = MockAdapter().collect()[0]
    external_id = raw_listing["external_id"]
    raw_data = dict(raw_listing)

    normalized = NormalizationService(MockNormalizer()).normalize_raw_listing(
        external_id=external_id,
        raw_data=raw_data,
    )

    assert normalized["external_id"] == "mock-001"
    assert normalized["asking_price_kopecks"] == 1_250_000_000
    assert normalized["asking_price_per_sqm_kopecks"] == 22_522_523