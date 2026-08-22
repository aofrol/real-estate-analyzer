"""Abstract interface for collecting raw source listings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.sources.base import SourceAdapter


class Collector(ABC):
    """Orchestrate collection through an injected source adapter.

    A collector passes raw source payloads forward. It does not access the
    database, construct ORM objects, normalize records, or deduplicate data.
    """

    def __init__(self, adapter: SourceAdapter) -> None:
        """Configure the source adapter used for collection."""
        self.adapter = adapter

    @abstractmethod
    def collect(self) -> list[dict[str, Any]]:
        """Collect and return raw listing payloads from the source adapter."""