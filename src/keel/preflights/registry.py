"""Phase preflight discovery — built-in + plugin entry points.

Plugin packages declare in their pyproject.toml:

    [project.entry-points."keel.phase_preflights"]
    my_rules = "my_pkg.preflights:get_preflights"

`get_preflights` must return list[PhasePreflight].
"""
from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import entry_points

from keel.preflights.base import PhasePreflight
from keel.preflights.builtin import builtin_preflights


def iter_preflights() -> Iterable[PhasePreflight]:
    """Yield all preflights (built-in first, then plugins)."""
    yield from builtin_preflights()
    for ep in entry_points(group="keel.phase_preflights"):
        try:
            getter = ep.load()
            yielded = getter()
        except Exception:
            continue
        for pf in yielded:
            yield pf
