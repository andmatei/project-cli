"""Phase preflight framework — built-in rules + plugin discovery."""

from __future__ import annotations

from keel.preflights.base import PhasePreflight, PreflightResult
from keel.preflights.builtin import builtin_preflights

# TODO: iter_preflights comes in Task 3.1
__all__ = [
    "PhasePreflight",
    "PreflightResult",
    "builtin_preflights",
]
