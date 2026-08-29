"""SQLAlchemy provider for property candidates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.property import Property
from app.normalization.types import NormalizedListing

from .property_candidates import PropertyCandidate, PropertyCandidateProvider


class SQLAlchemyPropertyCandidateProvider(PropertyCandidateProvider):
    """Load all properties in a resolved Building without deciding matches.

    The provider intentionally does not pre-filter by floor, rooms, studio
    status, or area. Matching responsibility belongs to
    ConservativePropertyMatcher, which must distinguish no candidates, no
    exact signature, and ambiguous candidates.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_candidates(
        self,
        *,
        listing: NormalizedListing,
        building_key: str,
    ) -> list[PropertyCandidate]:
        if not isinstance(building_key, str) or not building_key.strip():
            raise ValueError("building_key must be a non-empty string")

        try:
            building_id = UUID(building_key)
        except (AttributeError, TypeError, ValueError):
            raise ValueError("building_key must be a valid UUID") from None

        statement = (
            select(Property)
            .where(Property.building_id == building_id)
            .order_by(Property.id.asc())
        )
        properties = self._session.scalars(statement).all()

        return [
            PropertyCandidate(
                key=str(property_row.id),
                floor=property_row.floor,
                rooms=property_row.rooms,
                is_studio=property_row.is_studio,
                area_sqm=float(property_row.area_total),
            )
            for property_row in properties
        ]