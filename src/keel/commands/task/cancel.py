"""`keel task cancel <id>`."""

from __future__ import annotations

import typer

from keel.api import ErrorCode, Output, confirm_destructive, edit_milestones, find_task
from keel.workspace import resolve_cli_scope


def cmd_cancel(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Cancel a task (any state -> cancelled)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        task = find_task(manifest, id)
        if task is None:
            out.fail(f"no task with id '{id}'", code=ErrorCode.NOT_FOUND)

        confirm_destructive(f"Cancel task {id} (currently {task.status})?", yes=yes)

        task.status = "cancelled"

    out.result(task.model_dump(), human_text=f"Task cancelled: {id}")
