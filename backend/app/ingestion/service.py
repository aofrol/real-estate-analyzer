"""Application service for forwarding collected listings to persistence."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.collector.base import Collector
from app.models.listing import Listing
from app.models.listing_price_history import ListingPriceHistory
from app.normalization.types import NormalizedListing
from app.persistence import ListingPersistenceService, ListingPriceHistoryService
from app.repositories.raw_listing import RawListingRepository


@dataclass(frozen=True, slots=True)
class ListingPersistenceOrchestrationResult:
    """Persisted Listing plus an optional price transition row."""

    listing: Listing
    price_history: ListingPriceHistory | None


class ListingPersistenceOrchestrator:
    """Join current Listing and price-history writes in one caller transaction."""

    def __init__(
        self,
        listing_persistence: ListingPersistenceService,
        price_history: ListingPriceHistoryService,
    ) -> None:
        self._listing_persistence = listing_persistence
        self._price_history = price_history

    @classmethod
    def from_session(cls, session: Session) -> ListingPersistenceOrchestrator:
        """Build both persistence services on one caller-owned Session."""
        return cls(
            ListingPersistenceService(session),
            ListingPriceHistoryService(session),
        )

    def persist(
        self,
        *,
        source_key: str,
        property_key: str,
        listing: NormalizedListing,
    ) -> Listing:
        """Persist one normalized Listing and its price transition.

        The injected persistence services must share the caller's Session.  This
        method deliberately does not commit, roll back, or close that session.
        """
        return self.persist_with_history(
            source_key=source_key,
            property_key=property_key,
            listing=listing,
        ).listing

    def persist_with_history(
        self,
        *,
        source_key: str,
        property_key: str,
        listing: NormalizedListing,
    ) -> ListingPersistenceOrchestrationResult:
        """Persist one Listing and expose the history row created for it."""
        existing = self._listing_persistence.find_existing(
            source_key=source_key,
            external_id=listing.get("external_id"),
        )
        previous_price = existing.asking_price if existing is not None else None
        new_price = listing["asking_price_kopecks"]

        persisted_listing = self._listing_persistence.persist(
            source_key=source_key,
            property_key=property_key,
            listing=listing,
        )

        price_history = None
        if existing is not None and previous_price != new_price:
            if previous_price is None:
                raise ValueError("existing Listing must have an asking price")
            price_history = self._price_history.record_change(
                listing=persisted_listing,
                previous_price_kopecks=previous_price,
                new_price_kopecks=new_price,
            )

        return ListingPersistenceOrchestrationResult(
            listing=persisted_listing,
            price_history=price_history,
        )

    def persist_listing(
        self,
        *,
        source_key: str,
        property_key: str,
        listing: NormalizedListing,
    ) -> Listing:
        """Descriptive alias for callers that expose a listing pipeline step."""
        return self.persist(
            source_key=source_key,
            property_key=property_key,
            listing=listing,
        )


class IngestionService:
    """Coordinate collection and raw listing persistence."""

    def __init__(
        self,
        collector: Collector,
        repository: RawListingRepository,
        source_id: UUID,
    ) -> None:
        self.collector = collector
        self.repository = repository
        self._source_id = source_id

    def run(self) -> None:
        """Collect raw listings and persist each one without transforming it."""
        for raw_listing in self.collector.collect():
            external_id = raw_listing.get("external_id")
            if not isinstance(external_id, str) or not external_id.strip():
                raise ValueError("external_id must be non-empty")

            self.repository.save(
                source_id=self._source_id,
                external_id=external_id,
                raw_data=raw_listing,
            )