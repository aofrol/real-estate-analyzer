"""Shared minimal address canonicalization."""

from __future__ import annotations

__all__ = ["canonicalize_address"]


def canonicalize_address(value: str) -> str:
    """Canonicalize an address using the MVP matching rules."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("address must be non-empty")
    return " ".join(value.strip().lower().split())