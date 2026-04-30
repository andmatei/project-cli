"""`keel task add <id> --milestone <m-id> --title "..."`."""

from __future__ import annotations

import typer

from keel.api import (
    ErrorCode,
    GraphError,
    OpLog,
    Output,
    Task,
    edit_milestones,
    find_milestone,
    find_task,
    load_milestones_manifest,
    safe_push,
    validate_dag,
    with_provider,
)
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Print intended operations and exit; write nothing."),
    json_mode: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
) -> None:
    """Add a new task under an existing milestone."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    # Pre-load manifest to validate before write
    manifest = load_milestones_manifest(scope.milestones_manifest_path)
    if not any(m.id == milestone for m in manifest.milestones):
        out.fail(
            f"unknown milestone '{milestone}' (use 'keel milestone list' to see existing)",
            code=ErrorCode.NOT_FOUND,
        )

    if any(t.id == id for t in manifest.tasks):
        out.fail(
            f"task with id '{id}' already exists",
            code=ErrorCode.EXISTS,
        )

    deps_list = [d.strip() for d in depends_on.split(",") if d.strip()]
    existing_task_ids = {t.id for t in manifest.tasks}
    for dep in deps_list:
        if dep not in existing_task_ids:
            out.fail(
                f"unknown task '{dep}' in --depends-on",
                code=ErrorCode.NOT_FOUND,
            )

    new_task = Task(
        id=id,
        milestone=milestone,
        title=title,
        description=description,
        depends_on=deps_list,
    )
    # Validate the would-be DAG
    candidate_manifest = type(manifest)(milestones=manifest.milestones, tasks=manifest.tasks + [new_task])
    try:
        validate_dag(candidate_manifest)
    except GraphError as e:
        out.fail(f"invalid task graph: {e}", code=ErrorCode.INVALID_STATE)

    if dry_run:
        log = OpLog()
        log.modify_file(scope.milestones_manifest_path)
        out.info(log.format_summary())
        return

    with edit_milestones(scope) as manifest:
        manifest.tasks.append(new_task)

    provider = with_provider(scope, no_push=no_push)
    if provider is not None:
        # Parent: the milestone's ticket_id (set when milestone was pushed)
        with edit_milestones(scope) as manifest:
            parent_milestone = find_milestone(manifest, milestone)
            parent_id = parent_milestone.ticket_id if parent_milestone and parent_milestone.ticket_id else ""

        def _push():
            ticket = provider.create_task(parent_id, new_task.title, new_task.description)
            with edit_milestones(scope) as manifest:
                saved = find_task(manifest, id)
                if saved is not None:
                    saved.ticket_id = ticket.id

        safe_push(out, "create_task", _push)

    out.result(new_task.model_dump(), human_text=f"Task created: {id}")
