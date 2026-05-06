"""Jinja2-based template rendering for keel-jira.

The plugin owns its own templating layer so users can customize the
ticket payloads via `[extensions.ticketing.jira.templates]` in
`project.toml` without forking the plugin.

Templates have access to:
- `milestone`, `task` — typed objects from `keel.api` (when applicable)
- `milestone_id`, `task_id` — convenience aliases
- `scope` — the `keel.workspace.Scope` object
- `project`, `deliverable` — strings from the scope

Undefined variables raise immediately (StrictUndefined) so template typos
don't silently produce empty strings.
"""

from __future__ import annotations

from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined

# Default templates if the user provides none. Each entry is rendered with
# the same context dict; see `_build_context` in `provider.py`.
DEFAULT_TEMPLATES: dict[str, str] = {
    "milestone_summary": "{{ milestone.title }}",
    "milestone_description": "{{ milestone.description }}",
    "task_summary": "{{ task.title }}",
    "task_description": "{{ task.description }}\n\n— keel: `{{ task.id }}`",
}


def make_env(extra_filters: dict[str, Any] | None = None) -> Environment:
    """Build a Jinja Environment with strict undefined and no autoescape.

    Plain text output (Jira's ADF wrapper handles escaping later); we don't
    want HTML autoescaping. `extra_filters` lets callers register custom
    Jinja filters if needed.
    """
    env = Environment(
        loader=BaseLoader(),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    if extra_filters:
        env.filters.update(extra_filters)
    return env


def render(env: Environment, template_str: str, context: dict[str, Any]) -> str:
    """Render a template string against a context dict."""
    return env.from_string(template_str).render(**context)
