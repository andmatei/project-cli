"""`keel milestone done <id>`."""
from __future__ import annotations

import typer

from keel import workspace
from keel.errors import ErrorCode
from keel.manifest import load_milestones_manifest, load_project_manifest, save_milestones_manifest
from keel.output import Output
from keel.ticketing import get_provider_for_project
from keel.workspace import resolve_cli_scope


def cmd_done(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    force: bool = typer.Option(
        False, "--force", help="Skip fan-out completion check."
    ),
    no_push: bool = typer.Option(
        False, "--no-push",
        help="Skip pushing to the configured ticketing provider for this invocation.",
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
        out.fail(f"no milestone with id '{id}'", code=ErrorCode.NOT_FOUND)

    if milestone.status != "active":
        out.error(
            f"cannot mark milestone done from status '{milestone.status}' (must be 'active')",
            code=ErrorCode.INVALID_STATE,
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
                code=ErrorCode.INVALID_STATE,
            )
            raise typer.Exit(code=1)

    milestone.status = "done"
    save_milestones_manifest(path, manifest)

    if not no_push:
        proj_manifest = load_project_manifest(workspace.manifest_path(scope.project))
        provider = get_provider_for_project(proj_manifest)
        if provider is not None and milestone.jira_id:
            try:
                provider.transition(milestone.jira_id, "done")
            except Exception as e:  # noqa: BLE001
                out.info(f"[warning] ticket transition failed: {e}")

    out.result(milestone.model_dump(), human_text=f"Milestone done: {id}")
