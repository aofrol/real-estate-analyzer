"""ORM persistence boundary for Property records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.building import Building
from app.models.property import Property
from app.normalization.types import NormalizedListing
from app.resolution.property import PropertyResolutionResult


class PropertyPersistenceService:
    """Reuse or create one Property without owning the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def persist(
        self,
        *,
        listing: NormalizedListing,
        building_key: str,
        resolution: PropertyResolutionResult,
    ) -> Property:
        """Apply a property resolution result to the injected session."""
        building_id = self._parse_uuid(
            building_key,
            field_name="building_key",
        )

        if resolution.status == "ambiguous":
            raise ValueError("Cannot persist Property from ambiguous resolution")

        building = self._session.get(Building, building_id)
        if building is None:
            raise ValueError(
                f"Building not found for building_key: {building_key}"
            )

        if resolution.status == "matched":
            return self._load_matched_property(
                resolution=resolution,
                building_id=building_id,
            )

        if resolution.status == "create_required":
            property_row = Property(
                building_id=building_id,
                floor=listing["floor"],
                rooms=listing["rooms"],
                area_total=listing["area_sqm"],
                is_studio=listing["is_studio"],
            )
            self._session.add(property_row)
            self._session.flush()
            return property_row

        raise ValueError(f"Unsupported property resolution status: {resolution.status}")

    @staticmethod
    def _parse_uuid(value: str, *, field_name: str) -> UUID:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")

        try:
            return UUID(value)
        except (AttributeError, TypeError, ValueError):
            raise ValueError(f"{field_name} must be a valid UUID") from None

    def _load_matched_property(
        self,
        *,
        resolution: PropertyResolutionResult,
        building_id: UUID,
    ) -> Property:
        property_id = self._parse_uuid(
            resolution.property_key,
            field_name="property_key",
        )
        property_row = self._session.get(Property, property_id)
        if property_row is None:
            raise ValueError(
                "Property not found for property_key: "
                f"{resolution.property_key}"
            )

        if property_row.building_id != building_id:
            raise ValueError(
                "Property ownership mismatch for "
                f"property_key={resolution.property_key}, "
                f"building_key={building_id}"
            )

        return property_row