"""ORM persistence boundary for Listing price history."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.listing import Listing
from app.models.listing_price_history import ListingPriceHistory


class ListingPriceHistoryService:
    """Record current-price changes without owning the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record_change(
        self,
        *,
        listing: Listing,
        previous_price_kopecks: int,
        new_price_kopecks: int,
    ) -> ListingPriceHistory | None:
        """Persist one history row only when the observed price changed."""
        if listing.id is None:
            raise ValueError("listing must have an id for price history")

        self._validate_price(
            previous_price_kopecks,
            field_name="previous_price_kopecks",
        )
        self._validate_price(
            new_price_kopecks,
            field_name="new_price_kopecks",
        )

        if previous_price_kopecks == new_price_kopecks:
            return None

        history_row = ListingPriceHistory(
            listing_id=listing.id,
            asking_price=new_price_kopecks,
        )
        self._session.add(history_row)
        self._session.flush()
        return history_row

    @staticmethod
    def _validate_price(value: int, *, field_name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field_name} must be an integer")
        if value <= 0:
            raise ValueError(f"{field_name} must be positive")