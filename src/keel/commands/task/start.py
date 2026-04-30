"""`keel task start <id>`."""

from __future__ import annotations

import os

import typer

from keel.api import ErrorCode, Output, edit_milestones, find_task, slugify
from keel.workspace import resolve_cli_scope


def _default_branch(user: str, project: str, milestone_id: str, task_id: str) -> str:
    return f"{slugify(user)}/{project}-{milestone_id}-{task_id}"


def cmd_start(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(
        None, "-D", "--deliverable",
        help="Scope: a deliverable instead of the project. Auto-detected from CWD.",
    ),
    project: str | None = typer.Option(
        None, "--project", "-p",
        help="Project name. Auto-detected from CWD if omitted.",
    ),
    branch: str | None = typer.Option(
        None, "--branch", help="Override the auto-computed branch name."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Start work on a task (planned -> active). Records the branch name."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        task = find_task(manifest, id)
        if task is None:
            out.fail(f"no task with id '{id}'", code=ErrorCode.NOT_FOUND)

        if task.status != "planned":
            out.error(
                f"cannot start task in status '{task.status}' (must be 'planned')",
                code=ErrorCode.INVALID_STATE,
            )
            raise typer.Exit(code=1)

        user = os.environ.get("USER", "user")
        task.branch = branch or _default_branch(user, scope.project, task.milestone, task.id)
        task.status = "active"

    out.result(task.model_dump(), human_text=f"Task started: {id} (branch: {task.branch})")
