"""Framework-independent matching contracts."""

from .building import BuildingMatchResult, BuildingMatcher
from .candidates import BuildingCandidate, BuildingCandidateProvider
from .exact_building import ExactBuildingMatcher

__all__ = [
    "BuildingMatcher",
    "BuildingMatchResult",
    "BuildingCandidate",
    "BuildingCandidateProvider",
    "ExactBuildingMatcher",
]