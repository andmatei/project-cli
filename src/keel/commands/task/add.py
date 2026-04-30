"""`keel task add <id> --milestone <m-id> --title "..."`."""

from __future__ import annotations

import typer

from keel.errors import ErrorCode
from keel.manifest import (
    Task,
    load_milestones_manifest,
    load_project_manifest,
    save_milestones_manifest,
)
from keel.milestones import GraphError, validate_dag
from keel.output import Output
from keel.ticketing import get_provider_for_project
from keel.workspace import resolve_cli_scope


def cmd_add(
    ctx: typer.Context,
    id: str = typer.Argument(..., help="Task identifier (e.g., 't1', 'set-up')."),
    milestone: str = typer.Option(..., "--milestone", "-m", help="The owning milestone's id."),
    title: str = typer.Option(..., "--title", help="Human-readable task title."),
    description: str = typer.Option("", "--description", help="Optional description."),
    depends_on: str = typer.Option(
        "", "--depends-on",
        help="Comma-separated list of task ids this task depends on.",
    ),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable", help="Scope: a deliverable."),
    project: str | None = typer.Option(None, "--project", "-p", help="Project name."),
    no_push: bool = typer.Option(
        False, "--no-push",
        help="Skip pushing to the configured ticketing provider.",
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
) -> None:
    """Add a new task under an existing milestone."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    path = scope.milestones_manifest_path
    manifest = load_milestones_manifest(path)

    if not any(m.id == milestone for m in manifest.milestones):
        out.error(
            f"unknown milestone '{milestone}' (use 'keel milestone list' to see existing)",
            code=ErrorCode.NOT_FOUND,
        )
        raise typer.Exit(code=1)

    if any(t.id == id for t in manifest.tasks):
        out.error(
            f"task with id '{id}' already exists",
            code=ErrorCode.EXISTS,
        )
        raise typer.Exit(code=1)

    deps_list = [d.strip() for d in depends_on.split(",") if d.strip()]
    existing_task_ids = {t.id for t in manifest.tasks}
    for dep in deps_list:
        if dep not in existing_task_ids:
            out.error(
                f"unknown task '{dep}' in --depends-on",
                code=ErrorCode.NOT_FOUND,
            )
            raise typer.Exit(code=1)

    new_task = Task(
        id=id,
        milestone=milestone,
        title=title,
        description=description,
        depends_on=deps_list,
    )
    manifest.tasks.append(new_task)

    try:
        validate_dag(manifest)
    except GraphError as e:
        out.error(f"invalid task graph: {e}", code=ErrorCode.INVALID_STATE)
        raise typer.Exit(code=1) from e

    path.parent.mkdir(parents=True, exist_ok=True)
    save_milestones_manifest(path, manifest)

    if not no_push:
        from keel.workspace import manifest_path as proj_mp
        proj_manifest = load_project_manifest(proj_mp(scope.project))
        provider = get_provider_for_project(proj_manifest)
        if provider is not None:
            # Parent: the milestone's jira_id (set when milestone was pushed)
            parent_milestone = next((m for m in manifest.milestones if m.id == milestone), None)
            parent_id = parent_milestone.jira_id if parent_milestone and parent_milestone.jira_id else ""
            try:
                ticket = provider.create_task(parent_id, new_task.title, new_task.description)
                new_task.jira_id = ticket.id
                save_milestones_manifest(path, manifest)
            except Exception as e:  # noqa: BLE001
                out.info(f"[warning] ticket creation failed: {e}")

    out.result(new_task.model_dump(), human_text=f"Task created: {id}")
