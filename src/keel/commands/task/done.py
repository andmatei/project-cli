"""`keel task done <id>`."""

from __future__ import annotations

import typer

from keel.api import (
    ErrorCode,
    Output,
    edit_milestones,
    find_task,
    safe_push,
    with_provider,
)
from keel.workspace import resolve_cli_scope


def cmd_done(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    no_push: bool = typer.Option(
        False, "--no-push",
        help="Skip pushing to the configured ticketing provider for this invocation.",
    ),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Mark a task as done (active -> done)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        task = find_task(manifest, id)
        if task is None:
            out.fail(f"no task with id '{id}'", code=ErrorCode.NOT_FOUND)

        if task.status != "active":
            out.error(
                f"cannot mark task done from status '{task.status}' (must be 'active')",
                code=ErrorCode.INVALID_STATE,
            )
            raise typer.Exit(code=1)

        task.status = "done"

    provider = with_provider(scope, no_push=no_push)
    if provider is not None and task.jira_id:
        safe_push(out, "transition", lambda: provider.transition(task.jira_id, "done"))

    out.result(task.model_dump(), human_text=f"Task done: {id}")
