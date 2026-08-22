"""Minimal collector implementation for development and tests."""

from __future__ import annotations

from typing import Any

from app.sources.base import SourceAdapter

from .base import Collector


class MockCollector(Collector):
    """Pass raw listings through from the configured source adapter."""

    def __init__(self, adapter: SourceAdapter) -> None:
        super().__init__(adapter)

    def collect(self) -> list[dict[str, Any]]:
        """Return the adapter's raw listing payload unchanged."""
        return self.adapter.collect()