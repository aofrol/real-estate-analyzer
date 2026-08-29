"""Application boundary for resolving listings to properties."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.matching.property import PropertyMatcher
from app.normalization.types import NormalizedListing

_ALLOWED_STATUSES = {"matched", "create_required", "ambiguous"}
_CREATE_REQUIRED_REASONS = {
    "no_property_candidates",
    "no_exact_property_signature",
}
_AMBIGUOUS_REASON = "ambiguous_property_candidates"


@dataclass(frozen=True, slots=True)
class PropertyResolutionResult:
    """Immutable application-level outcome of property resolution."""

    status: str
    property_key: str | None
    match_confidence: float
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or self.status not in _ALLOWED_STATUSES:
            raise ValueError("status must be a supported resolution status")

        if (
            isinstance(self.match_confidence, bool)
            or not isinstance(self.match_confidence, (int, float))
            or not math.isfinite(self.match_confidence)
            or not 0.0 <= self.match_confidence <= 1.0
        ):
            raise ValueError("match_confidence must be between 0.0 and 1.0")

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty")

        if self.status == "matched":
            if not isinstance(self.property_key, str) or not self.property_key.strip():
                raise ValueError("property_key must be non-empty when matched")
            if self.match_confidence <= 0.0:
                raise ValueError(
                    "match_confidence must be greater than 0.0 when matched"
                )
        else:
            if self.property_key is not None:
                raise ValueError("property_key must be None when unresolved")
            if self.match_confidence != 0.0:
                raise ValueError(
                    "match_confidence must be 0.0 when unresolved"
                )


class PropertyResolutionService:
    """Translate a property matcher result into an application decision."""

    def __init__(self, matcher: PropertyMatcher) -> None:
        self._matcher = matcher

    def resolve(
        self,
        *,
        listing: NormalizedListing,
        building_key: str,
    ) -> PropertyResolutionResult:
        """Resolve one listing without persistence or database access."""
        match_result = self._matcher.match(
            listing=listing,
            building_key=building_key,
        )

        if match_result.matched:
            return PropertyResolutionResult(
                status="matched",
                property_key=match_result.candidate_key,
                match_confidence=match_result.confidence,
                reason=match_result.reason,
            )

        if match_result.reason in _CREATE_REQUIRED_REASONS:
            return PropertyResolutionResult(
                status="create_required",
                property_key=None,
                match_confidence=0.0,
                reason=match_result.reason,
            )

        if match_result.reason == _AMBIGUOUS_REASON:
            return PropertyResolutionResult(
                status="ambiguous",
                property_key=None,
                match_confidence=0.0,
                reason=match_result.reason,
            )

        raise ValueError(f"Unsupported matcher reason: {match_result.reason}")