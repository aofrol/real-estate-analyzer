"""ORM persistence boundary for Listing records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.listing import Listing
from app.models.property import Property
from app.models.source import Source
from app.normalization.types import NormalizedListing


class ListingPersistenceService:
    """Create or reuse one source Listing without owning the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def persist(
        self,
        *,
        source_key: str,
        property_key: str,
        listing: NormalizedListing,
    ) -> Listing:
        """Persist a normalized Listing identified by its source identity."""
        source_id = self._parse_uuid(source_key, field_name="source_key")
        property_id = self._parse_uuid(property_key, field_name="property_key")
        external_id = self._validate_external_id(listing.get("external_id"))

        source = self._session.get(Source, source_id)
        if source is None:
            raise ValueError(f"Source not found for source_key: {source_key}")

        property_row = self._session.get(Property, property_id)
        if property_row is None:
            raise ValueError(f"Property not found for property_key: {property_key}")

        existing = self._find_by_source_identity(
            source_id=source_id,
            external_id=external_id,
        )
        if existing is None:
            return self._create(
                source_id=source_id,
                property_id=property_id,
                listing=listing,
                external_id=external_id,
            )

        if existing.property_id != property_id:
            raise ValueError(
                "Listing property conflict for "
                f"source_key={source_key}, property_key={property_key}, "
                f"external_id={external_id}"
            )

        if self._update_mutable_state(existing, listing):
            self._session.flush()

        return existing

    def find_existing(
        self,
        *,
        source_key: str,
        external_id: object,
    ) -> Listing | None:
        """Find a Listing by source identity without mutating the session."""
        source_id = self._parse_uuid(source_key, field_name="source_key")
        external_id = self._validate_external_id(external_id)
        return self._find_by_source_identity(
            source_id=source_id,
            external_id=external_id,
        )

    def _find_by_source_identity(
        self,
        *,
        source_id: UUID,
        external_id: str,
    ) -> Listing | None:
        statement = select(Listing).where(
            Listing.source_id == source_id,
            Listing.external_id == external_id,
        )
        return self._session.scalars(statement).one_or_none()

    def _create(
        self,
        *,
        source_id: UUID,
        property_id: UUID,
        listing: NormalizedListing,
        external_id: str,
    ) -> Listing:
        listing_row = Listing(
            source_id=source_id,
            property_id=property_id,
            external_id=external_id,
            url=listing["source_url"],
            asking_price=listing["asking_price_kopecks"],
            asking_price_per_sqm=listing["asking_price_per_sqm_kopecks"],
            listed_at=listing["listed_at"],
            duplicate_of_id=None,
        )
        self._session.add(listing_row)
        self._session.flush()
        return listing_row

    @staticmethod
    def _update_mutable_state(
        existing: Listing,
        listing: NormalizedListing,
    ) -> bool:
        changed = False

        asking_price = listing["asking_price_kopecks"]
        if existing.asking_price != asking_price:
            existing.asking_price = asking_price
            changed = True

        asking_price_per_sqm = listing["asking_price_per_sqm_kopecks"]
        if existing.asking_price_per_sqm != asking_price_per_sqm:
            existing.asking_price_per_sqm = asking_price_per_sqm
            changed = True

        source_url = listing["source_url"]
        if source_url is not None and existing.url != source_url:
            existing.url = source_url
            changed = True

        listed_at = listing["listed_at"]
        if existing.listed_at is None and listed_at is not None:
            existing.listed_at = listed_at
            changed = True

        return changed

    @staticmethod
    def _parse_uuid(value: str, *, field_name: str) -> UUID:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")

        try:
            return UUID(value)
        except (AttributeError, TypeError, ValueError):
            raise ValueError(f"{field_name} must be a valid UUID") from None

    @staticmethod
    def _validate_external_id(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("external_id must be a non-empty string")
        return value