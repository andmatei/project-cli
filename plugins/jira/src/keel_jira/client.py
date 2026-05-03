"""Thin httpx-based wrapper around Jira Cloud REST API v3.

Just the endpoints the provider needs:
- POST /rest/api/3/issue          — create issue
- GET  /rest/api/3/issue/<key>    — fetch
- POST /rest/api/3/issue/<key>/transitions  — move to another status
- GET  /rest/api/3/issue/<key>/transitions  — list available transitions

We intentionally don't use the `jira` or `atlassian-python-api` libraries —
they add abstractions we don't need for these five calls.
"""

from __future__ import annotations

from typing import Any

import httpx


class JiraAPIError(RuntimeError):
    """Raised when the Jira REST API returns a non-2xx response."""

    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"Jira API error {status_code}: {body!r}")
        self.status_code = status_code
        self.body = body


class JiraClient:
    """Tiny synchronous Jira Cloud REST client."""

    def __init__(self, *, url: str, email: str, token: str, timeout: float = 30.0) -> None:
        self._base_url = url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            auth=(email, token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> JiraClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _request(self, method: str, path: str, *, json: dict | None = None) -> Any:
        response = self._client.request(method, path, json=json)
        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = response.text
            raise JiraAPIError(response.status_code, body)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def create_issue(
        self,
        *,
        project_key: str,
        issue_type: str,
        summary: str,
        description: str = "",
        parent_key: str | None = None,
    ) -> dict:
        """Create an issue. Returns the raw API response (includes `key`, `id`, `self`)."""
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary": summary,
        }
        if description:
            fields["description"] = _to_adf(description)
        if parent_key:
            fields["parent"] = {"key": parent_key}
        return self._request("POST", "/rest/api/3/issue", json={"fields": fields})

    def get_issue(self, key: str) -> dict:
        """Fetch an issue. Returns the raw API response."""
        return self._request("GET", f"/rest/api/3/issue/{key}")

    def list_transitions(self, key: str) -> list[dict]:
        """List transitions available from the issue's current status.

        Each entry has `id` and `to.name` keys.
        """
        data = self._request("GET", f"/rest/api/3/issue/{key}/transitions")
        return data.get("transitions", []) if isinstance(data, dict) else []

    def transition_issue(self, key: str, transition_id: str) -> None:
        """Apply a transition by id. Returns nothing on success."""
        self._request(
            "POST",
            f"/rest/api/3/issue/{key}/transitions",
            json={"transition": {"id": transition_id}},
        )

    def link_url(self, key: str) -> str:
        """Return the human-facing Jira URL for an issue key."""
        return f"{self._base_url}/browse/{key}"


def _to_adf(text: str) -> dict:
    """Wrap plain text in Atlassian Document Format (Jira Cloud's required body shape)."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }
