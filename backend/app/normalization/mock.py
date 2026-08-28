"""Deterministic normalizer for the mock source payload."""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from .base import Normalizer
from .types import NormalizedListing


class MockNormalizer(Normalizer):
    """Map the MockAdapter payload into the canonical listing schema."""

    def normalize(self, raw_listing: dict[str, Any]) -> NormalizedListing:
        """Return a new canonical dictionary without mutating raw_listing."""
        external_id = raw_listing.get("external_id")
        if not isinstance(external_id, str) or not external_id.strip():
            raise ValueError("external_id must be non-empty")

        address = raw_listing.get("address")
        if not isinstance(address, str) or not address.strip():
            raise ValueError("address must be non-empty")

        try:
            area_sqm = float(raw_listing["area"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("area must be greater than 0") from None
        if not math.isfinite(area_sqm) or area_sqm <= 0:
            raise ValueError("area must be greater than 0")

        try:
            price_rubles = Decimal(str(raw_listing["price"]))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            raise ValueError("price must be greater than 0") from None
        if not price_rubles.is_finite() or price_rubles <= 0:
            raise ValueError("price must be greater than 0")

        asking_price_kopecks = int(
            (price_rubles * 100).to_integral_value(rounding=ROUND_HALF_UP)
        )
        rooms = raw_listing.get("rooms")
        is_studio = raw_listing.get("property_type") == "studio"
        if is_studio:
            rooms = None
        elif rooms is not None:
            rooms = int(rooms)

        listed_at = raw_listing.get("listed_at")
        if isinstance(listed_at, str):
            try:
                listed_at = datetime.fromisoformat(listed_at.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("listed_at must be a valid ISO-8601 datetime") from None
        elif listed_at is not None and not isinstance(listed_at, datetime):
            raise ValueError("listed_at must be a datetime or ISO-8601 string")

        return {
            "external_id": external_id,
            "address": address,
            "city": raw_listing.get("city"),
            "area_sqm": area_sqm,
            "rooms": rooms,
            "is_studio": is_studio,
            "floor": raw_listing.get("floor"),
            "total_floors": raw_listing.get("total_floors"),
            "asking_price_kopecks": asking_price_kopecks,
            "asking_price_per_sqm_kopecks": round(
                asking_price_kopecks / area_sqm
            ),
            "latitude": raw_listing.get("latitude"),
            "longitude": raw_listing.get("longitude"),
            "source_url": raw_listing.get("url"),
            "building_type": raw_listing.get("building_type"),
            "listed_at": listed_at,
        }