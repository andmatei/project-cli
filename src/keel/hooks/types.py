"""HookEvent dataclass and HookAborted exception."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class HookEvent:
    """A single hook event firing.

    Attributes are immutable so a misbehaving subscriber can't corrupt
    state for downstream subscribers.
    """

    name: str
    """Event name without phase prefix (e.g., 'new', 'phase', 'deliverable-add')."""

    phase: Literal["pre", "post"]
    """Whether this event fires before or after the command's work."""

    project: str | None
    """Project slug, or None for events not scoped to a project."""

    deliverable: str | None
    """Deliverable slug, or None for project-scoped events."""

    payload: dict[str, Any] = field(default_factory=dict)
    """Event-specific structured data. Always a dict (may be empty)."""

    positional_args: tuple[str, ...] = ()
    """High-value identifiers passed as argv to user scripts. Stable, additive."""

    @property
    def full_name(self) -> str:
        """Combined hook name, e.g. 'pre-new' or 'post-phase'."""
        return f"{self.phase}-{self.name}"


class HookAborted(RuntimeError):
    """Raised by a pre-hook subscriber to abort the command.

    Subscribers may raise this to block a transition (e.g., preflight checks
    that find a blocker). The dispatcher catches and surfaces the message.
    """
