"""Contract tests for the source adapter layer."""

from __future__ import annotations

import importlib
import inspect
from typing import Any

from app.sources.base import SourceAdapter
from app.sources.mock import MockAdapter


def _mock_module_source() -> str:
    """Read MockAdapter's module source without importing persistence code."""
    module = importlib.import_module(MockAdapter.__module__)
    return inspect.getsource(module)


def test_mock_adapter_inherits_source_adapter() -> None:
    """MockAdapter must implement the public source adapter contract."""
    assert issubclass(MockAdapter, SourceAdapter)
    assert isinstance(MockAdapter(), SourceAdapter)


def test_mock_adapter_collect_returns_deterministic_raw_listing_list() -> None:
    """collect() returns source-shaped dictionaries without database access."""
    adapter = MockAdapter()

    first = adapter.collect()
    second = adapter.collect()

    assert isinstance(first, list)
    assert first == second
    assert first
    assert all(isinstance(raw_listing, dict) for raw_listing in first)
    assert first[0]["external_id"] == "mock-001"

    # The adapter module must remain independent of persistence and ORM code.
    module_source = _mock_module_source()
    assert "sqlalchemy" not in module_source.lower()
    assert "database" not in module_source.lower()


def test_mock_adapter_parse_accepts_raw_listing_without_orm_creation() -> None:
    """parse() returns a dictionary and does not construct ORM instances."""
    adapter = MockAdapter()
    raw_listing: dict[str, Any] = {
        "external_id": "contract-001",
        "price": 10_000_000,
        "source_payload": {"status": "active"},
    }

    parsed = adapter.parse(raw_listing)

    assert isinstance(parsed, dict)
    assert parsed == raw_listing
    assert parsed is not raw_listing
    assert not parsed.__class__.__module__.startswith("app.models")

    module_source = _mock_module_source()
    assert "sqlalchemy" not in module_source.lower()
    assert "database" not in module_source.lower()