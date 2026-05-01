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
    """Provider-agnostic ticket reference.

    The `status` field contains the provider's status string. For real providers this is the
    native state name (e.g. Jira's 'In Progress'). For MockProvider it equals keel's neutral
    state ('planned', 'active', 'done', 'cancelled') by design — this makes mock-based tests
    easier to write and assert on.
    """

    id: str
    url: str
    title: str | None = None
    status: str | None = None


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

    name: str
    """Provider name. MUST equal the entry-point name registered in
    `[project.entry-points."keel.ticket_providers"]`. keel uses this string
    both as the lookup key and as the value of `[extensions.ticketing.provider]`
    in `project.toml`."""

    def configure(self, config: dict) -> None:
        """Validate and store the [extensions.ticketing.<name>] config dict.

        Raises ValueError (or any exception) on bad config — keel does NOT catch it,
        so the user will see the failure immediately. This is intentional: a misconfigured
        provider should fail loud, not silently fall back to local-only mode.
        """
        ...

    def create_milestone(self, parent_id: str, title: str, description: str) -> Ticket:
        """Create a ticket representing a milestone.

        `parent_id` is the project-level ticket id (e.g. an Epic key for Jira) sourced from
        `[extensions.ticketing.parent_id]` in `project.toml`. Empty string if not configured.

        Returns a `Ticket` with at minimum `id` and `url` populated. `title` and `status`
        are recommended but optional.

        May raise on transport / auth failures. Keel wraps these in `safe_push`, which
        logs a warning and continues — the local manifest save is preserved.
        """
        ...

    def create_task(self, parent_milestone_id: str, title: str, description: str) -> Ticket:
        """Create a ticket representing a task.

        `parent_milestone_id` is the id of the milestone ticket created by this provider.

        Returns a `Ticket` with at minimum `id` and `url` populated. `title` and `status`
        are recommended but optional.

        May raise on transport / auth failures. Keel wraps these in `safe_push`, which
        logs a warning and continues — the local manifest save is preserved.
        """
        ...

    def transition(self, ticket_id: str, target_state: str) -> None:
        """Move a ticket to one of: 'planned', 'active', 'done', 'cancelled'.

        These are keel's neutral state names. Plugins are responsible for mapping them
        to provider-native states (e.g. Jira's 'To Do', 'In Progress', 'Done', 'Cancelled').
        Per-project overrides via [ticketing.status_map] are reserved for a future plan;
        plugins may accept a `status_map` key in the configure() dict.
        """
        ...

    def fetch(self, ticket_id: str) -> Ticket:
        """Re-read a ticket's state from the provider.

        Implementations SHOULD make a fresh request (not cache) when called via
        `keel * refresh` semantics. Used to detect drift between local manifest
        and the provider's source of truth.
        """
        ...

    def link_url(self, ticket_id: str) -> str:
        """Return a stable, clickable URL to view the ticket in the provider's UI.

        Pure function; should not require network. Used in CLI output and exports.
        """
        ...
