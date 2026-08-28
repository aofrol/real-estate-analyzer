"""Deterministic exact-address building matcher."""

from __future__ import annotations

from app.normalization.types import NormalizedListing

from .building import BuildingMatchResult, BuildingMatcher
from .candidates import BuildingCandidate, BuildingCandidateProvider


def _normalize_address(value: str) -> str:
    """Apply the minimal MVP address normalization rules."""
    return " ".join(value.strip().lower().split())


class ExactBuildingMatcher(BuildingMatcher):
    """Match normalized listings using exact normalized address equality."""

    def __init__(self, candidate_provider: BuildingCandidateProvider) -> None:
        self._candidate_provider = candidate_provider

    def match(self, listing: NormalizedListing) -> BuildingMatchResult:
        address = listing.get("address")
        if not isinstance(address, str) or not address.strip():
            raise ValueError("address must be non-empty")

        listing_address = _normalize_address(address)
        candidates = self._candidate_provider.get_candidates(listing)
        exact_candidates = [
            candidate
            for candidate in candidates
            if _normalize_address(candidate.address_normalized) == listing_address
        ]

        if not exact_candidates:
            if candidates:
                return BuildingMatchResult(
                    matched=False,
                    candidate_key=None,
                    confidence=0.0,
                    reason="no_exact_address_match",
                )
            return BuildingMatchResult(
                matched=False,
                candidate_key=None,
                confidence=0.0,
                reason="no_candidates",
            )

        if len(exact_candidates) == 1:
            return BuildingMatchResult(
                matched=True,
                candidate_key=exact_candidates[0].key,
                confidence=1.0,
                reason="exact_address",
            )

        scores = [
            (candidate, self._tie_break_score(candidate, listing))
            for candidate in exact_candidates
        ]
        highest_score = max(score for _, score in scores)
        winners = [
            candidate for candidate, score in scores if score == highest_score
        ]
        if len(winners) == 1:
            return BuildingMatchResult(
                matched=True,
                candidate_key=winners[0].key,
                confidence=0.95,
                reason="exact_address_tiebreak",
            )

        return BuildingMatchResult(
            matched=False,
            candidate_key=None,
            confidence=0.0,
            reason="ambiguous_exact_address",
        )

    @staticmethod
    def _tie_break_score(
        candidate: BuildingCandidate,
        listing: NormalizedListing,
    ) -> int:
        """Score only the explicitly allowed deterministic tie-breakers."""
        score = 0
        if listing.get("city") is not None and candidate.city == listing["city"]:
            score += 1
        if (
            listing.get("building_type") is not None
            and candidate.building_type == listing["building_type"]
        ):
            score += 1
        if (
            listing.get("total_floors") is not None
            and candidate.floors_total == listing["total_floors"]
        ):
            score += 1
        return score