"""Tests for keel.lifecycle."""
import pytest

from keel.lifecycle import DEFAULT_PHASE, PHASES, is_valid_phase, next_phase


def test_phases_in_order() -> None:
    assert PHASES == ["scoping", "designing", "poc", "implementing", "shipping", "done"]


def test_default_phase() -> None:
    assert DEFAULT_PHASE == "scoping"


def test_next_phase_advances() -> None:
    assert next_phase("scoping") == "designing"
    assert next_phase("implementing") == "shipping"


def test_next_phase_at_end() -> None:
    assert next_phase("done") is None


def test_next_phase_invalid_raises() -> None:
    with pytest.raises(ValueError):
        next_phase("bogus")


def test_is_valid_phase() -> None:
    assert is_valid_phase("scoping")
    assert not is_valid_phase("bogus")
