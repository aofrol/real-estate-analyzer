"""SQLAlchemy building candidate provider."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.building import Building
from app.normalization.types import NormalizedListing

from .address import canonicalize_address
from .candidates import BuildingCandidate, BuildingCandidateProvider


class SQLAlchemyBuildingCandidateProvider(BuildingCandidateProvider):
    """Load plausible building candidates using an injected SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_candidates(
        self,
        listing: NormalizedListing,
    ) -> list[BuildingCandidate]:
        address = listing.get("address")
        canonical_address = canonicalize_address(address)  # type: ignore[arg-type]
        predicates = [Building.address_normalized == canonical_address]

        city = listing.get("city")
        if city is not None:
            predicates.append(Building.city == city)

        statement = (
            select(Building)
            .where(*predicates)
            .order_by(Building.id.asc())
        )
        buildings = self._session.scalars(statement).all()

        return [
            BuildingCandidate(
                key=str(building.id),
                address_normalized=building.address_normalized,
                city=building.city,
                latitude=None,
                longitude=None,
                building_type=building.building_type,
                floors_total=building.floors_total,
            )
            for building in buildings
        ]