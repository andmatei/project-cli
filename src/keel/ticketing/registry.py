"""Plugin discovery via Python entry points.

Plugin packages declare in their pyproject.toml:

    [project.entry-points."keel.ticket_providers"]
    jira = "keel_jira.provider:JiraProvider"

keel.ticketing.registry.load_provider(name) finds and instantiates the matching
provider. Returns None if no provider is registered with that name (do not raise
— callers handle the "not installed" case).
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from keel.ticketing.base import TicketProvider


def load_provider(name: str) -> TicketProvider | None:
    """Find and instantiate the named TicketProvider, or return None if not found."""
    for ep in entry_points(group="keel.ticket_providers"):
        if ep.name != name:
            continue
        try:
            cls = ep.load()
        except Exception:
            return None
        try:
            instance = cls()
        except Exception:
            return None
        return instance
    return None


def list_providers() -> list[str]:
    """Names of all installed ticketing providers."""
    return sorted({ep.name for ep in entry_points(group="keel.ticket_providers")})
