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
