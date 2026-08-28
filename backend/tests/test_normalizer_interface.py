"""Tests for the framework-independent normalizer interface."""

from __future__ import annotations

from app.normalization import Normalizer


class ConcreteNormalizer(Normalizer):
    """Minimal test implementation of the normalizer contract."""

    def normalize(self, raw_listing: dict[str, object]) -> dict[str, object]:
        return dict(raw_listing)


def test_normalizer_is_abstract() -> None:
    """The interface itself cannot be instantiated."""
    try:
        Normalizer()
    except TypeError:
        pass
    else:
        raise AssertionError("Normalizer must remain abstract")


def test_concrete_normalizer_accepts_and_returns_dictionary() -> None:
    """A concrete implementation can process a raw listing dictionary."""
    normalizer = ConcreteNormalizer()
    raw_listing = {"external_id": "raw-001", "price": 1_000_000}

    normalized = normalizer.normalize(raw_listing)

    assert isinstance(normalized, dict)
    assert normalized == raw_listing
    assert normalized is not raw_listing
    assert raw_listing == {"external_id": "raw-001", "price": 1_000_000}