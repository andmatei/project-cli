"""`keel task done <id>`."""

from __future__ import annotations

import typer

from keel.errors import ErrorCode
from keel.manifest import load_milestones_manifest, save_milestones_manifest
from keel.output import Output
from keel.workspace import resolve_cli_scope


def cmd_done(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Mark a task as done (active -> done)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    path = scope.milestones_manifest_path
    manifest = load_milestones_manifest(path)

    task = next((t for t in manifest.tasks if t.id == id), None)
    if task is None:
        out.error(f"no task with id '{id}'", code=ErrorCode.NOT_FOUND)
        raise typer.Exit(code=1)

    if task.status != "active":
        out.error(
            f"cannot mark task done from status '{task.status}' (must be 'active')",
            code=ErrorCode.INVALID_STATE,
        )
        raise typer.Exit(code=1)

    task.status = "done"
    save_milestones_manifest(path, manifest)
    out.result(task.model_dump(), human_text=f"Task done: {id}")
