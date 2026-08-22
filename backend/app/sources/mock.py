"""Deterministic source adapter for development and tests."""

from __future__ import annotations

from typing import Any

from .base import SourceAdapter


class MockAdapter(SourceAdapter):
    """Return one stable source-shaped listing without external I/O."""

    def collect(self) -> dict[str, Any]:
        """Return one deterministic raw listing dictionary."""
        return {
            "external_id": "mock-001",
            "title": "Двухкомнатная квартира в Москве",
            "address": "г. Москва, ул. Ленина, д. 1",
            "city": "Москва",
            "property_type": "apartment",
            "rooms": 2,
            "area": 55.5,
            "floor": 5,
            "price": 12_500_000,
            "currency": "RUB",
            "status": "active",
            "url": "https://example.invalid/listings/mock-001",
        }

    def parse(self, raw_listing: dict[str, Any]) -> dict[str, Any]:
        """Return the source record as parsed data without domain normalization."""
        return dict(raw_listing)