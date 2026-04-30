"""Project lifecycle phases — single source of truth.

Plan 5 may add a customisable lifecycle DSL; for now this module is the only
place phase names live. Other modules import from here.
"""

from __future__ import annotations

PHASES: list[str] = ["scoping", "designing", "poc", "implementing", "shipping", "done"]
DEFAULT_PHASE: str = PHASES[0]


def is_valid_phase(name: str) -> bool:
    return name in PHASES


def next_phase(current: str) -> str | None:
    """Return the next phase after `current`, or None if `current` is terminal."""
    if current not in PHASES:
        raise ValueError(f"unknown phase: {current!r}. Valid: {PHASES}")
    idx = PHASES.index(current)
    if idx + 1 >= len(PHASES):
        return None
    return PHASES[idx + 1]


# Milestone and task state sets — currently identical, but kept as separate
# constants so they can diverge later if needed (e.g. tasks gaining a `blocked`
# state, milestones losing one).
MILESTONE_STATES: list[str] = ["planned", "active", "done", "cancelled"]
TASK_STATES: list[str] = MILESTONE_STATES  # same set; alias for clarity at call sites

DEFAULT_MILESTONE_STATE: str = MILESTONE_STATES[0]
DEFAULT_TASK_STATE: str = TASK_STATES[0]

_TERMINAL_STATES = frozenset({"done", "cancelled"})


def is_valid_milestone_state(name: str) -> bool:
    return name in MILESTONE_STATES


def is_valid_task_state(name: str) -> bool:
    return name in TASK_STATES


def is_terminal_milestone_state(name: str) -> bool:
    return name in _TERMINAL_STATES


def is_terminal_task_state(name: str) -> bool:
    return name in _TERMINAL_STATES
