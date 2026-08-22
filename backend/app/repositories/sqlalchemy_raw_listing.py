"""SQLAlchemy persistence implementation for raw listings."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import RawListing

from .raw_listing import RawListingRepository


class SQLAlchemyRawListingRepository(RawListingRepository):
    """Persist raw listing payloads using an injected SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, raw_listing: dict[str, Any]) -> RawListing:
        """Add and flush one raw listing, returning the created ORM object."""
        listing = RawListing(
            source_id=raw_listing["source_id"],
            external_id=raw_listing["external_id"],
            raw_data=raw_listing["raw_data"],
        )
        self.session.add(listing)
        self.session.flush()
        return listing