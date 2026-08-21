"""
SQLAlchemy ORM models package.

Импорт этого модуля регистрирует все модели в Base.metadata.
Alembic autogenerate и alembic upgrade head используют эту metadata.

Экспортируемые имена:
  Base                    — DeclarativeBase (содержит metadata всех таблиц)
  Source                  — sources
  Building                — buildings
  RawListing              — raw_listings
  Property                — properties
  Listing                 — listings
  ListingPriceHistory     — listing_price_history
  SearchRequest           — search_requests
  ValuationResult         — valuation_results
  ValuationComparable     — valuation_comparables
"""

from .base import Base
from .building import Building
from .listing import Listing
from .listing_price_history import ListingPriceHistory
from .property import Property
from .raw_listing import RawListing
from .search_request import SearchRequest
from .source import Source
from .valuation_comparable import ValuationComparable
from .valuation_result import ValuationResult

__all__ = [
    "Base",
    "Building",
    "Listing",
    "ListingPriceHistory",
    "Property",
    "RawListing",
    "SearchRequest",
    "Source",
    "ValuationComparable",
    "ValuationResult",
]
