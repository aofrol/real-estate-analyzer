"""Canonical, framework-independent normalized listing types."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class NormalizedListing(TypedDict):
    """Canonical application-level representation of one listing."""

    external_id: str
    address: str
    area_sqm: float
    rooms: int | None
    is_studio: bool
    floor: int | None
    total_floors: int | None
    asking_price_kopecks: int
    asking_price_per_sqm_kopecks: int
    city: str | None
    latitude: float | None
    longitude: float | None
    source_url: str | None
    building_type: str | None
    listed_at: datetime | None