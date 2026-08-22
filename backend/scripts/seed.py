"""Create deterministic mock records for local domain-model verification.

This script only seeds data; schema creation and migrations remain Alembic's
responsibility. Run from the workspace root with DATABASE_URL set:

    python backend/scripts/seed.py

The seed is idempotent for the mock source and source/external-id pairs. An
existing record is reused rather than duplicated.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

# Make `app` importable when this file is run directly from the workspace root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_session  # noqa: E402
from app.models import (  # noqa: E402
    Building,
    Listing,
    Property,
    RawListing,
    Source,
)


SOURCE_NAME = "Mock Source"
ADAPTER_CLASS = "mock.MockAdapter"
EXTERNAL_ID = "mock-001"

ADDRESS_RAW = "г. Москва, ул. Ленина, д. 1"
ADDRESS_NORMALIZED = "Москва, улица Ленина, 1"
CITY = "Москва"
BUILDING_TYPE = "brick"

# WKT uses longitude first, latitude second; Geography is SRID 4326.
LOCATION = WKTElement("POINT(37.6173 55.7558)", srid=4326)

FLOOR = 5
ROOMS = 2
AREA_TOTAL = Decimal("55.5")
ASKING_PRICE_KOPECKS = 1_250_000_000
ASKING_PRICE_PER_SQM_KOPECKS = 22_522_522


def _get_or_create_source(session: Any, created: dict[str, list[Any]]) -> Source:
    source = session.scalar(select(Source).where(Source.name == SOURCE_NAME))
    if source is None:
        source = Source(name=SOURCE_NAME, adapter_class=ADAPTER_CLASS)
        session.add(source)
        session.flush()
        created["Source"].append(source)
    return source


def _get_or_create_building(session: Any, created: dict[str, list[Any]]) -> Building:
    building = session.scalar(
        select(Building).where(
            Building.address_normalized == ADDRESS_NORMALIZED,
            Building.city == CITY,
        )
    )
    if building is None:
        building = Building(
            address_raw=ADDRESS_RAW,
            address_normalized=ADDRESS_NORMALIZED,
            city=CITY,
            building_type=BUILDING_TYPE,
            location=LOCATION,
        )
        session.add(building)
        session.flush()
        created["Building"].append(building)
    return building


def _get_or_create_property(
    session: Any,
    building: Building,
    created: dict[str, list[Any]],
) -> Property:
    property_record = session.scalar(
        select(Property).where(
            Property.building_id == building.id,
            Property.floor == FLOOR,
            Property.rooms == ROOMS,
            Property.area_total == AREA_TOTAL,
        )
    )
    if property_record is None:
        property_record = Property(
            building_id=building.id,
            floor=FLOOR,
            rooms=ROOMS,
            area_total=AREA_TOTAL,
            is_studio=False,
        )
        session.add(property_record)
        session.flush()
        created["Property"].append(property_record)
    return property_record


def _get_or_create_raw_listing(
    session: Any,
    source: Source,
    created: dict[str, list[Any]],
) -> RawListing:
    raw_listing = session.scalar(
        select(RawListing).where(
            RawListing.source_id == source.id,
            RawListing.external_id == EXTERNAL_ID,
        )
    )
    if raw_listing is None:
        raw_listing = RawListing(
            source_id=source.id,
            external_id=EXTERNAL_ID,
            raw_data={
                "external_id": EXTERNAL_ID,
                "source": SOURCE_NAME,
                "address": ADDRESS_RAW,
                "rooms": ROOMS,
                "area_total": str(AREA_TOTAL),
                "asking_price_kopecks": ASKING_PRICE_KOPECKS,
            },
            collected_at=datetime.now(timezone.utc),
        )
        session.add(raw_listing)
        session.flush()
        created["RawListing"].append(raw_listing)
    return raw_listing


def _get_or_create_listing(
    session: Any,
    source: Source,
    property_record: Property,
    created: dict[str, list[Any]],
) -> Listing:
    listing = session.scalar(
        select(Listing).where(
            Listing.source_id == source.id,
            Listing.external_id == EXTERNAL_ID,
        )
    )
    if listing is None:
        listing = Listing(
            source_id=source.id,
            property_id=property_record.id,
            external_id=EXTERNAL_ID,
            asking_price=ASKING_PRICE_KOPECKS,
            asking_price_per_sqm=ASKING_PRICE_PER_SQM_KOPECKS,
            status="active",
        )
        session.add(listing)
        session.flush()
        created["Listing"].append(listing)
    return listing


def seed() -> None:
    """Create the mock source, domain records, raw listing, and listing."""
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError(
            "DATABASE_URL environment variable is required to run the seed."
        )

    created: dict[str, list[Any]] = {
        "Source": [],
        "Building": [],
        "Property": [],
        "RawListing": [],
        "Listing": [],
    }

    with get_session() as session:
        source = _get_or_create_source(session, created)
        building = _get_or_create_building(session, created)
        property_record = _get_or_create_property(session, building, created)
        _get_or_create_raw_listing(session, source, created)
        _get_or_create_listing(session, source, property_record, created)
        session.commit()

    total_created = sum(len(records) for records in created.values())
    print(f"Created objects: {total_created}")
    for model_name, records in created.items():
        print(f"  {model_name}: {len(records)}")

    print("Created IDs:")
    for model_name, records in created.items():
        for record in records:
            print(f"  {model_name}: {record.id}")


if __name__ == "__main__":
    seed()