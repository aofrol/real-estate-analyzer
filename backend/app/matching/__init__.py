"""Framework-independent matching contracts."""

from .address import canonicalize_address
from .building import BuildingMatchResult, BuildingMatcher
from .candidates import BuildingCandidate, BuildingCandidateProvider
from .exact_building import ExactBuildingMatcher
from .property import PropertyMatchResult, PropertyMatcher
from .sqlalchemy_candidates import SQLAlchemyBuildingCandidateProvider

__all__ = [
    "BuildingMatcher",
    "BuildingMatchResult",
    "BuildingCandidate",
    "BuildingCandidateProvider",
    "ExactBuildingMatcher",
    "canonicalize_address",
    "SQLAlchemyBuildingCandidateProvider",
    "PropertyMatcher",
    "PropertyMatchResult",
]