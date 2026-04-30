"""`keel milestone done <id>`."""
from __future__ import annotations

import typer

from keel import workspace
from keel.errors import ErrorCode
from keel.manifest import load_milestones_manifest, save_milestones_manifest
from keel.output import Output
from keel.workspace import resolve_cli_scope


def cmd_done(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    force: bool = typer.Option(
        False, "--force", help="Skip fan-out completion check."
    ),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Mark a milestone as done (active -> done)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    path = scope.milestones_manifest_path
    manifest = load_milestones_manifest(path)

    milestone = next((m for m in manifest.milestones if m.id == id), None)
    if milestone is None:
        out.error(f"no milestone with id '{id}'", code=ErrorCode.NOT_FOUND)
        raise typer.Exit(code=1)

    if milestone.status != "active":
        out.error(
            f"cannot mark milestone done from status '{milestone.status}' (must be 'active')",
            code=ErrorCode.EXISTS,
        )
        raise typer.Exit(code=1)

    # Fan-out validation: every fan-out deliverable's matching sub-milestone must be done.
    if milestone.fan_out and not force:
        unfinished: list[str] = []
        for sub_name in milestone.fan_out:
            sub_path = workspace.milestones_manifest_path(scope.project, sub_name)
            sub_manifest = load_milestones_manifest(sub_path)
            sub = next((m for m in sub_manifest.milestones if m.parent == milestone.id), None)
            if sub is None:
                unfinished.append(f"{sub_name} (no sub-milestone with parent={milestone.id})")
            elif sub.status != "done":
                unfinished.append(f"{sub_name}/{sub.id} (status: {sub.status})")
        if unfinished:
            out.error(
                "cannot mark fan-out milestone done; sub-milestones not complete: "
                + ", ".join(unfinished)
                + " (use --force to override)",
                code=ErrorCode.EXISTS,
            )
            raise typer.Exit(code=1)

    milestone.status = "done"
    save_milestones_manifest(path, manifest)
    out.result(milestone.model_dump(), human_text=f"Milestone done: {id}")
