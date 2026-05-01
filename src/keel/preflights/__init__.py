"""Phase preflight framework — built-in rules + plugin discovery."""

from __future__ import annotations

from keel.preflights.base import PhasePreflight, PreflightResult

# TODO: builtin_preflights and iter_preflights come in Tasks 1.2 and 3.1
__all__ = [
    "PhasePreflight",
    "PreflightResult",
]
