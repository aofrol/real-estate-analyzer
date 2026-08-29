"""End-to-end tests for processing one persisted source observation."""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import FrozenInstanceError
from typing import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.ingestion import (
    ListingPersistenceOrchestrationResult,
    ListingPersistenceOrchestrator,
)
from app.matching import (
    ConservativePropertyMatcher,
    ExactBuildingMatcher,
    SQLAlchemyBuildingCandidateProvider,
    SQLAlchemyPropertyCandidateProvider,
    canonicalize_address,
)
from app.models.building import Building
from app.models.listing import Listing
from app.models.listing_price_history import ListingPriceHistory
from app.models.property import Property
from app.models.raw_listing import RawListing
from app.models.source import Source
from app.normalization import MockNormalizer, NormalizationService
from app.normalization.types import NormalizedListing
from app.persistence import (
    BuildingPersistenceResult,
    BuildingPersistenceService,
    ListingPersistenceService,
    PropertyPersistenceService,
)
from app.processing import ListingProcessingPipeline, ListingProcessingResult
from app.resolution import BuildingResolutionService, PropertyResolutionService


def _payload(
    *,
    external_id: str | None = None,
    address: str | None = None,
    price: int = 12_500_000,
    url: str | None = "https://example.test/listing",
) -> dict[str, object]:
    return {
        "external_id": external_id or f"pipeline-{uuid4()}",
        "address": address or f"Москва, тестовый дом {uuid4()}",
        "city": "Москва",
        "property_type": "apartment",
        "rooms": 2,
        "area": 55.5,
        "floor": 5,
        "total_floors": 10,
        "price": price,
        "currency": "RUB",
        "url": url,
        "building_type": "brick",
    }


def _build_pipeline(
    session: Session,
    *,
    orchestrator: ListingPersistenceOrchestrator | None = None,
) -> ListingProcessingPipeline:
    building_provider = SQLAlchemyBuildingCandidateProvider(session)
    property_provider = SQLAlchemyPropertyCandidateProvider(session)
    return ListingProcessingPipeline(
        normalization_service=NormalizationService(MockNormalizer()),
        building_resolution_service=BuildingResolutionService(
            ExactBuildingMatcher(building_provider)
        ),
        building_persistence_service=BuildingPersistenceService(session),
        property_resolution_service=PropertyResolutionService(
            ConservativePropertyMatcher(property_provider)
        ),
        property_persistence_service=PropertyPersistenceService(session),
        listing_persistence_orchestrator=(
            orchestrator or ListingPersistenceOrchestrator.from_session(session)
        ),
    )


def _persist_source_observation(
    session: Session,
    payload: dict[str, object],
) -> tuple[Source, RawListing]:
    source = Source(
        name=f"Pipeline test {uuid4()}",
        adapter_class="app.sources.mock.MockAdapter",
    )
    session.add(source)
    session.flush()

    raw_listing = RawListing(
        source_id=source.id,
        external_id=str(payload["external_id"]),
        raw_data=deepcopy(payload),
    )
    session.add(raw_listing)
    session.flush()
    return source, raw_listing


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("LISTING_PIPELINE_TEST_DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )
    if not url:
        pytest.skip(
            "LISTING_PIPELINE_TEST_DATABASE_URL or DATABASE_URL is not configured"
        )
    return url


@pytest.fixture
def db_session(database_url: str) -> Iterator[Session]:
    engine = create_engine(database_url, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
        engine.dispose()


def test_first_repeat_and_changed_price_use_stable_database_identities(
    db_session: Session,
) -> None:
    initial_building_count = db_session.scalar(
        select(func.count()).select_from(Building)
    )
    initial_property_count = db_session.scalar(
        select(func.count()).select_from(Property)
    )
    payload = _payload()
    payload_before = deepcopy(payload)
    source, raw_listing = _persist_source_observation(db_session, payload)
    pipeline = _build_pipeline(db_session)

    first = pipeline.process(
        source_key=str(source.id),
        external_id=raw_listing.external_id,
        raw_data=raw_listing.raw_data,
    )

    assert isinstance(first, ListingProcessingResult)
    assert raw_listing.raw_data == payload_before
    assert first.listing.source_id == source.id
    assert first.listing.external_id == raw_listing.external_id
    assert first.listing.duplicate_of_id is None
    assert first.price_history is None
    first_ids = (
        first.building.id,
        first.property.id,
        first.listing.id,
    )

    unchanged = pipeline.process(
        source_key=str(source.id),
        external_id=raw_listing.external_id,
        raw_data=raw_listing.raw_data,
    )

    assert (
        unchanged.building.id,
        unchanged.property.id,
        unchanged.listing.id,
    ) == first_ids
    assert unchanged.price_history is None
    assert unchanged.listing.property_id == first.property.id
    assert unchanged.listing.duplicate_of_id is None

    changed_payload = deepcopy(payload)
    changed_payload["price"] = 13_000_000
    changed = pipeline.process(
        source_key=str(source.id),
        external_id=raw_listing.external_id,
        raw_data=changed_payload,
    )

    assert (
        changed.building.id,
        changed.property.id,
        changed.listing.id,
    ) == first_ids
    assert changed.listing.asking_price == 1_300_000_000
    assert (
        changed.listing.asking_price_per_sqm
        == changed.normalized_listing["asking_price_per_sqm_kopecks"]
    )
    assert changed.price_history is not None
    assert changed.price_history.listing_id == first.listing.id
    assert changed.price_history.asking_price == 1_300_000_000
    assert raw_listing.raw_data == payload_before
    assert changed_payload["external_id"] == payload["external_id"]

    history_prices = db_session.scalars(
        select(ListingPriceHistory.asking_price).where(
            ListingPriceHistory.listing_id == first.listing.id
        )
    ).all()
    assert history_prices == [1_300_000_000]
    assert 1_250_000_000 not in history_prices
    assert (
        db_session.scalar(select(func.count()).select_from(Building))
        == initial_building_count + 1
    )
    assert (
        db_session.scalar(select(func.count()).select_from(Property))
        == initial_property_count + 1
    )
    assert db_session.scalar(
        select(func.count())
        .select_from(Listing)
        .where(
            Listing.source_id == source.id,
            Listing.external_id == raw_listing.external_id,
        )
    ) == 1


def test_ambiguous_building_fails_before_property_and_listing(
    db_session: Session,
) -> None:
    initial_property_count = db_session.scalar(
        select(func.count()).select_from(Property)
    )
    payload = _payload()
    source, raw_listing = _persist_source_observation(db_session, payload)
    address = str(payload["address"])
    for _ in range(2):
        db_session.add(
            Building(
                address_raw=address,
                address_normalized=canonicalize_address(address),
                city="Москва",
                floors_total=10,
                building_type="brick",
            )
        )
    db_session.flush()

    with pytest.raises(ValueError, match="ambiguous building"):
        _build_pipeline(db_session).process(
            source_key=str(source.id),
            external_id=raw_listing.external_id,
            raw_data=raw_listing.raw_data,
        )

    assert (
        db_session.scalar(select(func.count()).select_from(Property))
        == initial_property_count
    )
    assert db_session.scalar(
        select(func.count())
        .select_from(Listing)
        .where(Listing.source_id == source.id)
    ) == 0


def test_ambiguous_property_fails_before_listing(
    db_session: Session,
) -> None:
    payload = _payload()
    source, raw_listing = _persist_source_observation(db_session, payload)
    address = str(payload["address"])
    building = Building(
        address_raw=address,
        address_normalized=canonicalize_address(address),
        city="Москва",
        floors_total=10,
        building_type="brick",
    )
    db_session.add(building)
    db_session.flush()
    for _ in range(2):
        db_session.add(
            Property(
                building_id=building.id,
                floor=5,
                rooms=2,
                area_total=55.5,
                is_studio=False,
            )
        )
    db_session.flush()

    with pytest.raises(ValueError, match="ambiguous"):
        _build_pipeline(db_session).process(
            source_key=str(source.id),
            external_id=raw_listing.external_id,
            raw_data=raw_listing.raw_data,
        )

    assert db_session.scalar(
        select(func.count())
        .select_from(Listing)
        .where(Listing.source_id == source.id)
    ) == 0


class FailingPriceHistory:
    def record_change(
        self,
        *,
        listing: Listing,
        previous_price_kopecks: int,
        new_price_kopecks: int,
    ) -> ListingPriceHistory:
        raise RuntimeError("forced price-history failure")


def _cleanup_committed_observation(
    engine: Engine,
    *,
    source_id: UUID,
    building_id: UUID | None,
) -> None:
    with Session(engine) as session:
        listing_ids = select(Listing.id).where(Listing.source_id == source_id)
        session.execute(
            delete(ListingPriceHistory).where(
                ListingPriceHistory.listing_id.in_(listing_ids)
            )
        )
        session.execute(delete(Listing).where(Listing.source_id == source_id))
        session.execute(
            delete(RawListing).where(RawListing.source_id == source_id)
        )
        if building_id is not None:
            session.execute(
                delete(Property).where(Property.building_id == building_id)
            )
            session.execute(
                delete(Building).where(Building.id == building_id)
            )
        session.execute(delete(Source).where(Source.id == source_id))
        session.commit()


def test_caller_rollback_removes_partial_current_price_update(
    database_url: str,
) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    source_id: UUID | None = None
    building_id: UUID | None = None
    raw_listing_id: UUID | None = None
    listing_id: UUID | None = None
    try:
        with Session(engine, autoflush=False, expire_on_commit=False) as setup:
            payload = _payload()
            source, raw_listing = _persist_source_observation(setup, payload)
            first = _build_pipeline(setup).process(
                source_key=str(source.id),
                external_id=raw_listing.external_id,
                raw_data=raw_listing.raw_data,
            )
            source_id = source.id
            building_id = first.building.id
            raw_listing_id = raw_listing.id
            listing_id = first.listing.id
            setup.commit()

        with Session(engine, autoflush=False, expire_on_commit=False) as update:
            raw_listing = update.get(RawListing, raw_listing_id)
            assert raw_listing is not None
            changed_payload = deepcopy(raw_listing.raw_data)
            changed_payload["price"] = 13_500_000
            orchestrator = ListingPersistenceOrchestrator(
                ListingPersistenceService(update),
                FailingPriceHistory(),  # type: ignore[arg-type]
            )

            with pytest.raises(RuntimeError, match="forced price-history failure"):
                _build_pipeline(update, orchestrator=orchestrator).process(
                    source_key=str(source_id),
                    external_id=raw_listing.external_id,
                    raw_data=changed_payload,
                )

            mutated = update.get(Listing, listing_id)
            assert mutated is not None
            assert mutated.asking_price == 1_350_000_000
            update.rollback()

        with Session(engine) as verification:
            persisted = verification.get(Listing, listing_id)
            assert persisted is not None
            assert persisted.asking_price == 1_250_000_000
            assert verification.scalar(
                select(func.count())
                .select_from(ListingPriceHistory)
                .where(ListingPriceHistory.listing_id == listing_id)
            ) == 0
    finally:
        if source_id is not None:
            _cleanup_committed_observation(
                engine,
                source_id=source_id,
                building_id=building_id,
            )
        engine.dispose()


def test_pipeline_rejects_invalid_authoritative_source_before_work() -> None:
    class MustNotNormalize:
        def normalize_raw_listing(self, **kwargs: object) -> NormalizedListing:
            raise AssertionError("normalization must not run")

    pipeline = ListingProcessingPipeline(
        normalization_service=MustNotNormalize(),  # type: ignore[arg-type]
        building_resolution_service=object(),  # type: ignore[arg-type]
        building_persistence_service=object(),  # type: ignore[arg-type]
        property_resolution_service=object(),  # type: ignore[arg-type]
        property_persistence_service=object(),  # type: ignore[arg-type]
        listing_persistence_orchestrator=object(),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="source_key"):
        pipeline.process(
            source_key="not-a-uuid",
            external_id="source-listing-1",
            raw_data=_payload(external_id="source-listing-1"),
        )


def test_processing_result_is_immutable() -> None:
    building = Building(id=uuid4(), address_raw="Москва")
    property_row = Property(
        id=uuid4(),
        building_id=building.id,
        floor=5,
        rooms=2,
        area_total=55.5,
        is_studio=False,
    )
    listing = Listing(id=uuid4(), asking_price=100)
    result = ListingProcessingResult(
        normalized_listing={
            "external_id": "listing-1",
            "address": "Москва",
            "area_sqm": 55.5,
            "rooms": 2,
            "is_studio": False,
            "floor": 5,
            "total_floors": 10,
            "asking_price_kopecks": 100,
            "asking_price_per_sqm_kopecks": 2,
            "city": "Москва",
            "latitude": None,
            "longitude": None,
            "source_url": None,
            "building_type": None,
            "listed_at": None,
        },
        building=building,
        property=property_row,
        listing=listing,
        price_history=None,
    )

    with pytest.raises(FrozenInstanceError):
        result.listing = Listing(id=uuid4())  # type: ignore[misc]