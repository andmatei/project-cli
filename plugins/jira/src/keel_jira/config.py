"""Pydantic configuration model for the Jira plugin.

Reads the `[extensions.ticketing.jira]` block from `project.toml` plus the
`KEEL_JIRA_EMAIL` and `KEEL_JIRA_TOKEN` environment variables.

Credentials are intentionally NOT in the manifest — only structural config
(URL, project key, status map) is. Tokens belong in env or a secret store.
"""

from __future__ import annotations

import os
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DEFAULT_STATUS_MAP: dict[str, str] = {
    "planned": "To Do",
    "active": "In Progress",
    "done": "Done",
    "cancelled": "Cancelled",
}


class JiraConfig(BaseModel):
    """Configuration for the Jira TicketProvider.

    The structural fields come from `project.toml`'s
    `[extensions.ticketing.jira]` block. Credentials come from the environment.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = Field(
        min_length=1, description="Jira workspace base URL, e.g. 'https://acme.atlassian.net'."
    )
    project_key: str = Field(min_length=1, description="Jira project key, e.g. 'PROJ'.")
    issue_type_milestone: str = Field(
        default="Story", description="Issue type used for milestones."
    )
    issue_type_task: str = Field(default="Sub-task", description="Issue type used for tasks.")
    status_map: dict[str, str] = Field(
        default_factory=lambda: dict(_DEFAULT_STATUS_MAP),
        description="Map from keel's neutral states to Jira's workflow status names.",
    )
    templates: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Per-project Jinja overrides for ticket payload fields. Recognized keys: "
            "milestone_summary, milestone_description, task_summary, task_description. "
            "Anything not overridden falls back to keel_jira.templates.DEFAULT_TEMPLATES."
        ),
    )
    labels: list[str] = Field(
        default_factory=list,
        description=(
            "Labels to attach to every issue created by this plugin. Each entry is "
            "rendered through Jinja with the same context as the summary/description templates."
        ),
    )
    custom_fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Custom Jira fields (e.g. 'customfield_12345') merged into the issue's "
            "`fields` block. String values are rendered through Jinja; non-string "
            "values pass through unchanged."
        ),
    )

    # Populated from env, not the manifest.
    email: str | None = Field(default=None, exclude=True)
    token: str | None = Field(default=None, exclude=True)

    @field_validator("url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("status_map")
    @classmethod
    def _status_map_covers_neutral_states(cls, v: dict[str, str]) -> dict[str, str]:
        required = {"planned", "active", "done", "cancelled"}
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"status_map is missing entries for: {sorted(missing)}")
        return v

    @classmethod
    def from_extension_block(cls, raw: dict, *, env: dict[str, str] | None = None) -> Self:
        """Build a JiraConfig from a parsed `[extensions.ticketing.jira]` dict.

        Reads `email` and `token` from `env` (defaults to `os.environ`).
        Raises `ValueError` if structural fields are invalid; raises
        `JiraCredentialsMissing` if the env vars aren't set.
        """
        env = env if env is not None else dict(os.environ)
        cfg = cls.model_validate(raw)
        cfg.email = env.get("KEEL_JIRA_EMAIL")
        cfg.token = env.get("KEEL_JIRA_TOKEN")
        if not cfg.email or not cfg.token:
            raise JiraCredentialsMissing(
                "KEEL_JIRA_EMAIL and KEEL_JIRA_TOKEN must both be set in the environment"
            )
        return cfg

    def jira_status_for(self, neutral_state: str) -> str:
        """Look up the Jira status name for one of keel's neutral states.

        Raises KeyError if the state is unknown.
        """
        return self.status_map[neutral_state]

    def render_field(self, value: str | list | dict, context: dict) -> Any:
        """Render a config value (string / list of strings / dict of strings) through Jinja.

        Used for `labels` and `custom_fields` — keeps templating behavior
        consistent with summary/description but lives next to the value
        being rendered. Non-string entries in lists/dicts pass through.
        """
        from keel_jira.templates import make_env, render

        env = make_env()
        if isinstance(value, str):
            return render(env, value, context)
        if isinstance(value, list):
            return [render(env, str(v), context) if isinstance(v, str) else v for v in value]
        if isinstance(value, dict):
            return {
                k: (render(env, str(v), context) if isinstance(v, str) else v)
                for k, v in value.items()
            }
        return value


class JiraCredentialsMissingError(RuntimeError):
    """Raised when KEEL_JIRA_EMAIL / KEEL_JIRA_TOKEN are not set."""


# Backwards-compat alias kept for any pre-release imports.
JiraCredentialsMissing = JiraCredentialsMissingError
