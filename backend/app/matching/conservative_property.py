"""Conservative deterministic matcher for property candidates."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.normalization.types import NormalizedListing

from .property import PropertyMatchResult, PropertyMatcher
from .property_candidates import PropertyCandidate, PropertyCandidateProvider

_AREA_QUANTUM = Decimal("0.01")


def _normalize_area(value: int | float) -> Decimal:
    """Normalize an area using the fixed MVP comparison precision."""
    return Decimal(str(value)).quantize(
        _AREA_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


class ConservativePropertyMatcher(PropertyMatcher):
    """Match one unique descriptive signature without forcing ambiguity.

    A unique exact descriptive signature is accepted only as an MVP heuristic
    match within one already-resolved Building. It is not guaranteed physical-
    apartment identity. If more than one candidate shares the same signature,
    the result is ambiguous.

    Future identity strengthening may use an apartment number, cadastral
    identifier, source crosswalk, or richer canonical property identity data.
    """

    def __init__(self, candidate_provider: PropertyCandidateProvider) -> None:
        self._candidate_provider = candidate_provider

    def match(
        self,
        *,
        listing: NormalizedListing,
        building_key: str,
    ) -> PropertyMatchResult:
        if not isinstance(building_key, str) or not building_key.strip():
            raise ValueError("building_key must be a non-empty string")

        candidates = self._candidate_provider.get_candidates(
            listing=listing,
            building_key=building_key,
        )
        if not candidates:
            return PropertyMatchResult(
                matched=False,
                candidate_key=None,
                confidence=0.0,
                reason="no_property_candidates",
            )

        listing_area = _normalize_area(listing["area_sqm"])
        matches = [
            candidate
            for candidate in candidates
            if self._matches_signature(candidate, listing, listing_area)
        ]

        if not matches:
            return PropertyMatchResult(
                matched=False,
                candidate_key=None,
                confidence=0.0,
                reason="no_exact_property_signature",
            )

        if len(matches) > 1:
            return PropertyMatchResult(
                matched=False,
                candidate_key=None,
                confidence=0.0,
                reason="ambiguous_property_candidates",
            )

        return PropertyMatchResult(
            matched=True,
            candidate_key=matches[0].key,
            confidence=0.80,
            reason="exact_descriptive_signature",
        )

    @staticmethod
    def _matches_signature(
        candidate: PropertyCandidate,
        listing: NormalizedListing,
        listing_area: Decimal,
    ) -> bool:
        return (
            candidate.floor == listing["floor"]
            and candidate.rooms == listing["rooms"]
            and candidate.is_studio == listing["is_studio"]
            and _normalize_area(candidate.area_sqm) == listing_area
        )