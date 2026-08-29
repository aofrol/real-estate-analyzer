"""End-to-end application orchestration for one persisted listing observation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.ingestion import (
    ListingPersistenceOrchestrator,
)
from app.models.building import Building
from app.models.listing import Listing
from app.models.listing_price_history import ListingPriceHistory
from app.models.property import Property
from app.normalization.service import NormalizationService
from app.normalization.types import NormalizedListing
from app.persistence.building import BuildingPersistenceService
from app.persistence.property import PropertyPersistenceService
from app.resolution.building import BuildingResolutionService
from app.resolution.property import PropertyResolutionService


@dataclass(frozen=True, slots=True)
class ListingProcessingResult:
    """The domain entities produced for one source observation."""

    normalized_listing: NormalizedListing
    building: Building
    property: Property
    listing: Listing
    price_history: ListingPriceHistory | None


class ListingProcessingPipeline:
    """Coordinate normalization and entity persistence without owning a session."""

    def __init__(
        self,
        *,
        normalization_service: NormalizationService,
        building_resolution_service: BuildingResolutionService,
        building_persistence_service: BuildingPersistenceService,
        property_resolution_service: PropertyResolutionService,
        property_persistence_service: PropertyPersistenceService,
        listing_persistence_orchestrator: ListingPersistenceOrchestrator,
    ) -> None:
        self._normalization_service = normalization_service
        self._building_resolution_service = building_resolution_service
        self._building_persistence_service = building_persistence_service
        self._property_resolution_service = property_resolution_service
        self._property_persistence_service = property_persistence_service
        self._listing_persistence_orchestrator = listing_persistence_orchestrator

    def process(
        self,
        *,
        source_key: str,
        external_id: str,
        raw_data: dict[str, Any],
    ) -> ListingProcessingResult:
        """Process one raw observation using authoritative persisted identity."""
        self._validate_source_key(source_key)

        normalized_listing = (
            self._normalization_service.normalize_raw_listing(
                external_id=external_id,
                raw_data=raw_data,
            )
        )

        building_resolution = self._building_resolution_service.resolve(
            normalized_listing
        )
        building_persistence = self._building_persistence_service.persist(
            listing=normalized_listing,
            resolution=building_resolution,
        )

        property_resolution = self._property_resolution_service.resolve(
            listing=normalized_listing,
            building_key=building_persistence.building_key,
        )
        property_row = self._property_persistence_service.persist(
            listing=normalized_listing,
            building_key=building_persistence.building_key,
            resolution=property_resolution,
        )

        if property_row.id is None:
            raise ValueError("persisted Property must have an id")
        building = property_row.building
        if building is None:
            raise ValueError("persisted Property must have a Building relationship")

        listing_result = (
            self._listing_persistence_orchestrator.persist_with_history(
                source_key=source_key,
                property_key=str(property_row.id),
                listing=normalized_listing,
            )
        )

        return ListingProcessingResult(
            normalized_listing=normalized_listing,
            building=building,
            property=property_row,
            listing=listing_result.listing,
            price_history=listing_result.price_history,
        )

    @staticmethod
    def _validate_source_key(source_key: str) -> None:
        if not isinstance(source_key, str) or not source_key.strip():
            raise ValueError("source_key must be a non-empty string")
        try:
            UUID(source_key)
        except (AttributeError, TypeError, ValueError):
            raise ValueError("source_key must be a valid UUID") from None