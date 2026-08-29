"""Application-level resolution services."""

from .building import BuildingResolutionResult, BuildingResolutionService
from .property import PropertyResolutionResult, PropertyResolutionService

__all__ = [
    "BuildingResolutionResult",
    "BuildingResolutionService",
    "PropertyResolutionResult",
    "PropertyResolutionService",
]