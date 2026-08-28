"""Controlled persistence boundary for Building records."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.matching.address import canonicalize_address
from app.models.building import Building
from app.normalization.types import NormalizedListing
from app.resolution import BuildingResolutionResult


@dataclass(frozen=True, slots=True)
class BuildingPersistenceResult:
    """Reference to a persisted Building and whether it was newly created."""

    building_key: str
    created: bool

    def __post_init__(self) -> None:
        if not isinstance(self.building_key, str) or not self.building_key.strip():
            raise ValueError("building_key must be a non-empty string")
        if not isinstance(self.created, bool):
            raise ValueError("created must be a bool")


class BuildingPersistenceService:
    """Reuse or create one Building without owning the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def persist(
        self,
        *,
        listing: NormalizedListing,
        resolution: BuildingResolutionResult,
    ) -> BuildingPersistenceResult:
        """Persist the building outcome represented by a resolution result."""
        if resolution.status == "matched":
            return self._reuse_matched_building(resolution)

        if resolution.status == "create_required":
            return self._create_building(listing)

        if resolution.status == "ambiguous":
            raise ValueError("ambiguous building resolution cannot be persisted")

        raise ValueError(f"Unsupported building resolution status: {resolution.status}")

    def _reuse_matched_building(
        self,
        resolution: BuildingResolutionResult,
    ) -> BuildingPersistenceResult:
        try:
            building_id = UUID(resolution.building_key)
        except (AttributeError, TypeError, ValueError):
            raise ValueError("building_key must be a valid UUID") from None

        building = self._session.get(Building, building_id)
        if building is None:
            raise ValueError("building_key does not identify an existing Building")

        return BuildingPersistenceResult(
            building_key=str(building.id),
            created=False,
        )

    def _create_building(
        self,
        listing: NormalizedListing,
    ) -> BuildingPersistenceResult:
        address = listing["address"]
        address_normalized = canonicalize_address(address)
        building = Building(
            address_raw=address,
            address_normalized=address_normalized,
            city=listing["city"],
            floors_total=listing["total_floors"],
            building_type=listing["building_type"],
            location=None,
        )
        self._session.add(building)
        self._session.flush()

        if building.id is None:
            raise ValueError("building_key is unavailable after flush")

        return BuildingPersistenceResult(
            building_key=str(building.id),
            created=True,
        )