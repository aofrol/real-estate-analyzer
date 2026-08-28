"""Application service boundary for normalizing persisted raw listings."""

from __future__ import annotations

from typing import Any

from .base import Normalizer
from .types import NormalizedListing


class NormalizationService:
    """Reconstruct raw input and delegate normalization without persistence."""

    def __init__(self, normalizer: Normalizer) -> None:
        self._normalizer = normalizer

    def normalize_raw_listing(
        self,
        *,
        external_id: str,
        raw_data: dict[str, Any],
    ) -> NormalizedListing:
        """Normalize a persisted raw payload using its authoritative ID."""
        if not isinstance(external_id, str) or not external_id.strip():
            raise ValueError("external_id must be non-empty")
        if not isinstance(raw_data, dict):
            raise ValueError("raw_data must be a dictionary")

        normalizer_input = dict(raw_data)
        normalizer_input["external_id"] = external_id
        return self._normalizer.normalize(normalizer_input)