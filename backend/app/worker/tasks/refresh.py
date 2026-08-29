"""
Periodic background refresh task (stub — implemented in Task #5).

Celery Beat will call refresh_recent_locations() on schedule.
"""
from app.ingestion import ListingPersistenceOrchestrator
from app.models.listing import Listing
from app.normalization.types import NormalizedListing
from app.worker.celery_app import celery_app
from sqlalchemy.orm import Session


def persist_refreshed_listing(
    *,
    session: Session,
    source_key: str,
    property_key: str,
    listing: NormalizedListing,
) -> Listing:
    """Persist one refresh using services bound to the caller's Session."""
    return ListingPersistenceOrchestrator.from_session(session).persist(
        source_key=source_key,
        property_key=property_key,
        listing=listing,
    )


@celery_app.task(name="refresh_recent_locations")
def refresh_recent_locations() -> dict:
    """
    Re-run the data collection pipeline for recently searched locations.
    Stub — full implementation in Task #5 (Data Pipeline).
    """
    return {"status": "stub", "message": "Implemented in Task #5"}
