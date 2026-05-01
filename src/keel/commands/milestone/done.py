"""`keel milestone done <id>`."""

from __future__ import annotations

import typer

from keel import workspace
from keel.api import (
    ErrorCode,
    OpLog,
    Output,
    edit_milestones,
    find_milestone,
    load_milestones_manifest,
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
    force: bool = typer.Option(False, "--force", help="Skip fan-out completion check."),
    no_push: bool = typer.Option(
        False,
        "--no-push",
        help="Skip pushing to the configured ticketing provider for this invocation.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Mark a milestone as done (active -> done)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    # Pre-validate before write
    manifest = load_milestones_manifest(scope.milestones_manifest_path)
    milestone = find_milestone(manifest, id)
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

    if dry_run:
        log = OpLog()
        log.modify_file(scope.milestones_manifest_path)
        out.info(log.format_summary())
        return

    with edit_milestones(scope) as manifest:
        milestone = find_milestone(manifest, id)
        milestone.status = "done"

    provider = with_provider(scope, no_push=no_push)
    if provider is not None and milestone.ticket_id:
        safe_push(out, "transition", lambda: provider.transition(milestone.ticket_id, "done"))

    out.result(milestone.model_dump(), human_text=f"Milestone done: {id}")
