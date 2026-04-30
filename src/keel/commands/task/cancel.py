"""`keel task cancel <id>`."""

from __future__ import annotations

import typer

from keel.errors import ErrorCode
from keel.manifest import load_milestones_manifest, save_milestones_manifest
from keel.output import Output
from keel.prompts import confirm_destructive
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
    path = scope.milestones_manifest_path
    manifest = load_milestones_manifest(path)

    task = next((t for t in manifest.tasks if t.id == id), None)
    if task is None:
        out.fail(f"no task with id '{id}'", code=ErrorCode.NOT_FOUND)

    confirm_destructive(f"Cancel task {id} (currently {task.status})?", yes=yes)

    task.status = "cancelled"
    save_milestones_manifest(path, manifest)
    out.result(task.model_dump(), human_text=f"Task cancelled: {id}")
