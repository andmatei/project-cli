"""`keel task move <id> --milestone <m>`."""

from __future__ import annotations

import typer

from keel.api import (
    ErrorCode,
    Output,
    edit_milestones,
    find_milestone,
    get_task,
    resolve_cli_scope,
)


def cmd_move(
    ctx: typer.Context,
    id: str = typer.Argument(..., help="Task identifier to move."),
    milestone: str = typer.Option(
        ..., "--milestone", "-m", help="Target milestone id to move the task under."
    ),
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
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Move a task to a different milestone."""
    out = Output.from_context(ctx, json_mode=json_mode)
    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        task = get_task(manifest, id, out=out)
        if find_milestone(manifest, milestone) is None:
            out.fail(f"unknown milestone '{milestone}'", code=ErrorCode.NOT_FOUND)

        old_milestone_id = task.milestone
        task.milestone = milestone

        # If the old milestone was the implicit default and now empty, drop it.
        if old_milestone_id == "default" and not any(
            t.milestone == "default" for t in manifest.tasks
        ):
            manifest.milestones = [ms for ms in manifest.milestones if ms.id != "default"]

    out.result(task.model_dump(), human_text=f"Task moved: {id} → {milestone}")
