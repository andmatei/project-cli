"""In-memory mock provider for tests and as a reference for plugin authors.

Records every method call in `self.calls` so tests can assert on them.
Tickets are assigned sequential `MOCK-N` ids.

Example:

    from keel.ticketing.mock import MockProvider
    p = MockProvider()
    t = p.create_milestone("EPIC-1", "Foundation", "")
    assert ("create_milestone", "EPIC-1", "Foundation", "") in p.calls
    assert t.id.startswith("MOCK-")
"""

from __future__ import annotations

from typing import Any

from keel.ticketing.base import Ticket


class MockProvider:
    """Reference implementation of the TicketProvider protocol — fully in-memory."""

    name: str = "mock"

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self._tickets: dict[str, Ticket] = {}
        self._counter: int = 0
        self._config: dict[str, Any] = {}

    def _next_id(self) -> str:
        self._counter += 1
        return f"MOCK-{self._counter}"

    def configure(self, config: dict) -> None:
        self.calls.append(("configure", config))
        self._config = dict(config)

    def create_milestone(self, parent_id: str, title: str, description: str) -> Ticket:
        self.calls.append(("create_milestone", parent_id, title, description))
        tid = self._next_id()
        t = Ticket(id=tid, url=self.link_url(tid), title=title, status="planned")
        self._tickets[tid] = t
        return t

    def create_task(self, parent_milestone_id: str, title: str, description: str) -> Ticket:
        self.calls.append(("create_task", parent_milestone_id, title, description))
        tid = self._next_id()
        t = Ticket(id=tid, url=self.link_url(tid), title=title, status="planned")
        self._tickets[tid] = t
        return t

    def transition(self, ticket_id: str, target_state: str) -> None:
        self.calls.append(("transition", ticket_id, target_state))
        existing = self._tickets.get(ticket_id)
        if existing is not None:
            self._tickets[ticket_id] = Ticket(
                id=existing.id,
                url=existing.url,
                title=existing.title,
                status=target_state,
            )

    def fetch(self, ticket_id: str) -> Ticket:
        self.calls.append(("fetch", ticket_id))
        if ticket_id not in self._tickets:
            return Ticket(id=ticket_id, url=self.link_url(ticket_id), status="unknown")
        return self._tickets[ticket_id]

    def link_url(self, ticket_id: str) -> str:
        return f"mock://tickets/{ticket_id}"
