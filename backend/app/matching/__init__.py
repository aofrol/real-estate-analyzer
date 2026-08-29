"""Framework-independent matching contracts."""

from .address import canonicalize_address
from .building import BuildingMatchResult, BuildingMatcher
from .candidates import BuildingCandidate, BuildingCandidateProvider
from .conservative_property import ConservativePropertyMatcher
from .exact_building import ExactBuildingMatcher
from .property import PropertyMatchResult, PropertyMatcher
from .property_candidates import PropertyCandidate, PropertyCandidateProvider
from .sqlalchemy_candidates import SQLAlchemyBuildingCandidateProvider
from .sqlalchemy_property_candidates import SQLAlchemyPropertyCandidateProvider

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
    "PropertyCandidate",
    "PropertyCandidateProvider",
    "ConservativePropertyMatcher",
    "SQLAlchemyPropertyCandidateProvider",
]