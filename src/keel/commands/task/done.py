"""`keel task done <id>`."""

from __future__ import annotations

import typer

from keel.api import (
    ErrorCode,
    Output,
    edit_milestones,
    get_task,
    resolve_cli_scope,
    safe_push,
    with_provider,
)


def cmd_done(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(
        None,
        "-D",
        "--deliverable",
        help="Scope: a deliverable instead of the project. Auto-detected from CWD.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Project name. Auto-detected from CWD if omitted.",
    ),
    no_push: bool = typer.Option(
        False,
        "--no-push",
        help="Skip pushing to the configured ticketing provider for this invocation.",
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Mark a task as done (active -> done)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        task = get_task(manifest, id, out=out)

        if task.status != "active":
            out.error(
                f"cannot mark task done from status '{task.status}' (must be 'active')",
                code=ErrorCode.INVALID_STATE,
            )
            raise typer.Exit(code=1)

        task.status = "done"

    provider = with_provider(scope, no_push=no_push)
    if provider is not None and task.ticket_id:
        safe_push(out, "transition", lambda: provider.transition(task.ticket_id, "done"))

    out.result(task.model_dump(), human_text=f"Task done: {id}")
