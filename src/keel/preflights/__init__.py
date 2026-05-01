"""Phase preflight framework — built-in rules + plugin discovery."""

from __future__ import annotations

from keel.preflights.base import PhasePreflight, PreflightResult
from keel.preflights.builtin import builtin_preflights
from keel.preflights.registry import iter_preflights

__all__ = [
    "PhasePreflight",
    "PreflightResult",
    "builtin_preflights",
    "iter_preflights",
]
