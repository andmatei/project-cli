"""Phase preflight protocol and result type.

Preflights run before a phase transition and may emit warnings or blockers.
- A warning prompts the user to confirm. `--force` skips warnings.
- A blocker exits non-zero. `--force` overrides blockers too.
- `--strict` upgrades warnings to blockers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from keel.workspace import Scope


@dataclass(frozen=True)
class PreflightResult:
    """Outcome of running a preflight check.

    `warnings` are advisory; `blockers` are fatal unless --force is passed.
    """

    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True iff the preflight emitted neither warnings nor blockers."""
        return not self.warnings and not self.blockers


@runtime_checkable
class PhasePreflight(Protocol):
    """A pluggable check run before a phase transition.

    Implementations decide internally whether they care about a given
    (from_phase, to_phase) pair — return an empty result to opt out.
    """

    name: str

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        """Inspect the project at `scope` and return any warnings/blockers
        for the proposed transition.
        """
        ...
