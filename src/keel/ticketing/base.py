"""Ticketing plugin protocol.

Plugin authors implement TicketProvider; keel core uses it via the registry.
keel core ships zero real providers — only this protocol and a MockProvider
in keel.ticketing.mock for tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Ticket:
    """Provider-agnostic ticket reference."""

    id: str
    url: str
    title: str | None = None
    status: str | None = None  # provider's native status, not keel's neutral state


@runtime_checkable
class TicketProvider(Protocol):
    """Protocol for ticketing plugins.

    A plugin package registers a TicketProvider via the `keel.ticket_providers`
    entry-point group. keel core uses this protocol; it never imports the
    plugin's internals.

    The neutral status names are: planned, active, done, cancelled.
    Each provider is responsible for mapping these to its native states
    (and back).
    """

    name: str  # e.g. "jira", "github", "linear"

    def configure(self, config: dict) -> None:
        """Validate and accept the [extensions.ticketing.<name>] config dict."""
        ...

    def create_milestone(self, parent_id: str, title: str, description: str) -> Ticket:
        """Create a ticket representing a milestone (typically a Story under an Epic).

        `parent_id` is the project-level Epic id (or equivalent), from
        [ticketing] parent_id in the project manifest.
        """
        ...

    def create_task(self, parent_milestone_id: str, title: str, description: str) -> Ticket:
        """Create a ticket representing a task (typically a Subtask under the milestone's Story)."""
        ...

    def transition(self, ticket_id: str, target_state: str) -> None:
        """Move a ticket to one of: planned, active, done, cancelled."""
        ...

    def fetch(self, ticket_id: str) -> Ticket:
        """Re-read a ticket's state. Used by `keel * refresh` commands."""
        ...

    def link_url(self, ticket_id: str) -> str:
        """Return a clickable URL to view the ticket in the provider's UI."""
        ...
