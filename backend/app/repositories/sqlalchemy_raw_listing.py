"""SQLAlchemy persistence implementation for raw listings."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import RawListing

from .raw_listing import RawListingRepository


class SQLAlchemyRawListingRepository(RawListingRepository):
    """Persist raw listing payloads using an injected SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        *,
        source_id: UUID,
        external_id: str,
        raw_data: dict[str, Any],
    ) -> None:
        """Add and flush one raw listing."""
        listing = RawListing(
            source_id=source_id,
            external_id=external_id,
            raw_data=raw_data,
        )
        self.session.add(listing)
        self.session.flush()