"""`keel task rm <id>`."""
from __future__ import annotations

import typer

from keel.errors import ErrorCode
from keel.manifest import edit_milestones, find_task
from keel.output import Output
from keel.prompts import confirm_destructive
from keel.workspace import resolve_cli_scope


def cmd_rm(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    force: bool = typer.Option(
        False, "--force", help="Remove even if other tasks depend on this one."
    ),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Remove a task. Refuses if other tasks depend on it (use --force to override)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        task = find_task(manifest, id)
        if task is None:
            out.fail(f"no task with id '{id}'", code=ErrorCode.NOT_FOUND)

        dependents = [t.id for t in manifest.tasks if id in t.depends_on]
        if dependents and not force:
            out.error(
                f"cannot remove task '{id}'; depended on by: {', '.join(dependents)} "
                "(use --force to remove anyway)",
                code=ErrorCode.INVALID_STATE,
            )
            raise typer.Exit(code=1)

        confirm_destructive(f"Remove task {id}?", yes=yes)

        manifest.tasks = [t for t in manifest.tasks if t.id != id]

    out.result({"removed": id}, human_text=f"Task removed: {id}")
