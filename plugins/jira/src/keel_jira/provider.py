"""JiraProvider — implements `keel.ticketing.base.TicketProvider`."""

from __future__ import annotations

from keel.api import Ticket

from keel_jira.client import JiraAPIError, JiraClient
from keel_jira.config import JiraConfig, JiraCredentialsMissing


class JiraProvider:
    """A `TicketProvider` backed by Jira Cloud REST API v3.

    Lifecycle: keel calls `configure()` once with the parsed
    `[extensions.ticketing.jira]` block; subsequent calls (`create_milestone`,
    `transition`, etc.) hit the API.
    """

    name: str = "jira"

    def __init__(self) -> None:
        self._config: JiraConfig | None = None
        self._client: JiraClient | None = None

    def configure(self, config: dict) -> None:
        """Validate and store the [extensions.ticketing.jira] block.

        Reads credentials from KEEL_JIRA_EMAIL / KEEL_JIRA_TOKEN env vars.
        Raises if structural fields are invalid or credentials are missing.
        """
        cfg = JiraConfig.from_extension_block(config)
        # Credentials are guaranteed non-None by from_extension_block.
        assert cfg.email is not None
        assert cfg.token is not None
        self._config = cfg
        self._client = JiraClient(url=cfg.url, email=cfg.email, token=cfg.token)

    def create_milestone(self, parent_id: str, title: str, description: str) -> Ticket:
        """Create an issue representing a milestone (typically a Story under an Epic).

        `parent_id` is the project-level Epic key from
        `[extensions.ticketing.parent_id]`. Empty string means "no parent" —
        the issue is created at the project level.
        """
        cfg, client = self._require_configured()
        result = client.create_issue(
            project_key=cfg.project_key,
            issue_type=cfg.issue_type_milestone,
            summary=title,
            description=description,
            parent_key=parent_id or None,
        )
        key = result["key"]
        return Ticket(
            id=key,
            url=client.link_url(key),
            title=title,
            status=cfg.jira_status_for("planned"),
        )

    def create_task(self, parent_milestone_id: str, title: str, description: str) -> Ticket:
        """Create an issue representing a task (typically a Subtask under a Story).

        `parent_milestone_id` is the Jira key of the milestone's issue (from
        a prior `create_milestone` call).
        """
        cfg, client = self._require_configured()
        result = client.create_issue(
            project_key=cfg.project_key,
            issue_type=cfg.issue_type_task,
            summary=title,
            description=description,
            parent_key=parent_milestone_id or None,
        )
        key = result["key"]
        return Ticket(
            id=key,
            url=client.link_url(key),
            title=title,
            status=cfg.jira_status_for("planned"),
        )

    def transition(self, ticket_id: str, target_state: str) -> None:
        """Move an issue to the Jira status mapped from a keel neutral state.

        `target_state` is one of: 'planned', 'active', 'done', 'cancelled'.
        Resolves the right `transitions[].id` for the issue's current
        workflow position; raises `JiraAPIError` if no transition leads to
        the target status.
        """
        cfg, client = self._require_configured()
        target_status = cfg.jira_status_for(target_state)

        transitions = client.list_transitions(ticket_id)
        match = next(
            (
                t
                for t in transitions
                if t.get("to", {}).get("name", "").lower() == target_status.lower()
            ),
            None,
        )
        if match is None:
            available = [t.get("to", {}).get("name") for t in transitions]
            raise JiraAPIError(
                400,
                f"no transition leads to status '{target_status}' from issue {ticket_id} "
                f"(available: {available})",
            )
        client.transition_issue(ticket_id, match["id"])

    def fetch(self, ticket_id: str) -> Ticket:
        """Re-read an issue's current state from Jira."""
        _, client = self._require_configured()
        result = client.get_issue(ticket_id)
        fields = result.get("fields", {}) if isinstance(result, dict) else {}
        return Ticket(
            id=result.get("key", ticket_id),
            url=client.link_url(result.get("key", ticket_id)),
            title=fields.get("summary"),
            status=(fields.get("status") or {}).get("name"),
        )

    def link_url(self, ticket_id: str) -> str:
        """Return a clickable URL for the issue. Pure — no network call."""
        _, client = self._require_configured()
        return client.link_url(ticket_id)

    def _require_configured(self) -> tuple[JiraConfig, JiraClient]:
        if self._config is None or self._client is None:
            raise JiraCredentialsMissing("JiraProvider was used before configure() was called")
        return self._config, self._client
