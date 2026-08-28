"""Application boundary for resolving listings to existing buildings."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.matching import BuildingMatcher
from app.normalization.types import NormalizedListing


_ALLOWED_STATUSES = {"matched", "create_required", "ambiguous"}
_CREATE_REQUIRED_REASONS = {"no_candidates", "no_exact_address_match"}
_AMBIGUOUS_REASON = "ambiguous_exact_address"


@dataclass(frozen=True, slots=True)
class BuildingResolutionResult:
    """Immutable application-level outcome of building resolution.

    ``create_required`` means that no existing building was safely resolved
    and a later persistence service may create one. It does not mean that a
    Building row has already been created.
    """

    status: str
    building_key: str | None
    match_confidence: float
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or self.status not in _ALLOWED_STATUSES:
            raise ValueError("status must be a supported resolution status")

        if (
            not isinstance(self.match_confidence, (int, float))
            or not math.isfinite(self.match_confidence)
            or not 0.0 <= self.match_confidence <= 1.0
        ):
            raise ValueError("match_confidence must be between 0.0 and 1.0")

        if self.status == "matched":
            if not isinstance(self.building_key, str) or not self.building_key.strip():
                raise ValueError("building_key must be non-empty when matched")
            if self.match_confidence <= 0.0:
                raise ValueError("match_confidence must be greater than 0.0 when matched")
        else:
            if self.building_key is not None:
                raise ValueError("building_key must be None when unresolved")
            if self.match_confidence != 0.0:
                raise ValueError(
                    "match_confidence must be 0.0 when unresolved"
                )

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty")


class BuildingResolutionService:
    """Translate a matcher result into an application resolution outcome."""

    def __init__(self, matcher: BuildingMatcher) -> None:
        self._matcher = matcher

    def resolve(
        self,
        listing: NormalizedListing,
    ) -> BuildingResolutionResult:
        """Resolve one normalized listing without performing persistence."""
        match_result = self._matcher.match(listing)

        if match_result.matched:
            return BuildingResolutionResult(
                status="matched",
                building_key=match_result.candidate_key,
                match_confidence=match_result.confidence,
                reason=match_result.reason,
            )

        if match_result.reason in _CREATE_REQUIRED_REASONS:
            return BuildingResolutionResult(
                status="create_required",
                building_key=None,
                match_confidence=0.0,
                reason=match_result.reason,
            )

        if match_result.reason == _AMBIGUOUS_REASON:
            return BuildingResolutionResult(
                status="ambiguous",
                building_key=None,
                match_confidence=0.0,
                reason=match_result.reason,
            )

        raise ValueError(f"Unsupported matcher reason: {match_result.reason}")