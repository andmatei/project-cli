"""Tests for keel.lifecycle."""
import pytest

from keel.lifecycle import (
    DEFAULT_MILESTONE_STATE,
    DEFAULT_PHASE,
    DEFAULT_TASK_STATE,
    MILESTONE_STATES,
    PHASES,
    TASK_STATES,
    is_terminal_milestone_state,
    is_terminal_task_state,
    is_valid_milestone_state,
    is_valid_phase,
    is_valid_task_state,
    next_phase,
)


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


def test_milestone_states() -> None:
    assert MILESTONE_STATES == ["planned", "active", "done", "cancelled"]
    assert DEFAULT_MILESTONE_STATE == "planned"


def test_task_states() -> None:
    """Task states currently mirror milestone states."""
    assert TASK_STATES == MILESTONE_STATES
    assert DEFAULT_TASK_STATE == "planned"


def test_is_valid_milestone_state() -> None:
    for s in MILESTONE_STATES:
        assert is_valid_milestone_state(s)
    assert not is_valid_milestone_state("bogus")
    assert not is_valid_milestone_state("")


def test_is_valid_task_state() -> None:
    for s in TASK_STATES:
        assert is_valid_task_state(s)
    assert not is_valid_task_state("bogus")
    assert not is_valid_task_state("")


def test_is_terminal_state() -> None:
    assert is_terminal_milestone_state("done")
    assert is_terminal_milestone_state("cancelled")
    assert not is_terminal_milestone_state("planned")
    assert not is_terminal_milestone_state("active")
    assert is_terminal_task_state("done")
    assert is_terminal_task_state("cancelled")
