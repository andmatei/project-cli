"""Phase transition event hooks.

Plugin packages declare in their pyproject.toml:

    [project.entry-points."keel.phase_transitions"]
    my_hook = "my_pkg.hooks:on_transition"

The function receives (scope, from_phase, to_phase). Errors are caught and
logged via out.warn — a failing hook will not roll back the phase change.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from keel.output import Output
    from keel.workspace import Scope

PhaseTransitionHook = Callable["Scope", str, str, None]


def iter_phase_transition_hooks() -> list[PhaseTransitionHook]:
    """Return all registered phase-transition hooks."""
    out: list[PhaseTransitionHook] = []
    for ep in entry_points(group="keel.phase_transitions"):
        try:
            hook = ep.load()
        except Exception:
            continue
        out.append(hook)
    return out


def fire_phase_transition(scope: Scope, from_phase: str, to_phase: str, *, out: Output) -> None:
    """Fire all registered post-transition hooks. Warns on failures; never raises."""
    for hook in iter_phase_transition_hooks():
        try:
            hook(scope, from_phase, to_phase)
        except Exception as e:  # noqa: BLE001
            name = getattr(hook, "__name__", repr(hook))
            out.warn(f"phase-transition hook '{name}' failed: {e}")
