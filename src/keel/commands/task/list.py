"""`keel task list`."""

from __future__ import annotations

import typer
from rich.table import Table

from keel.api import ErrorCode, Output, blocked_tasks, load_milestones_manifest, ready_tasks
from keel.workspace import resolve_cli_scope


def cmd_list(
    ctx: typer.Context,
    deliverable: str | None = typer.Option(
        None, "-D", "--deliverable", help="Scope: a deliverable. Auto-detected from CWD."
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Project name. Auto-detected from CWD if omitted."
    ),
    milestone: str | None = typer.Option(None, "--milestone", "-m", help="Filter by milestone id."),
    status: str | None = typer.Option(
        None, "--status", help="Filter by status (planned/active/done/cancelled)."
    ),
    ready: bool = typer.Option(
        False, "--ready", help="Show only tasks whose dependencies are all done (terminal)."
    ),
    blocked: bool = typer.Option(
        False, "--blocked", help="Show only tasks blocked by non-terminal dependencies."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
) -> None:
    """List tasks at the current scope, optionally filtered."""
    out = Output.from_context(ctx, json_mode=json_mode)

    if ready and blocked:
        out.error(
            "--ready and --blocked are mutually exclusive",
            code=ErrorCode.CONFLICTING_FLAGS,
        )
        raise typer.Exit(code=2)

    scope = resolve_cli_scope(project, deliverable, out=out)
    manifest = load_milestones_manifest(scope.milestones_manifest_path)

    ready_ids = {t.id for t in ready_tasks(manifest)}

    rows = list(manifest.tasks)
    if milestone:
        rows = [t for t in rows if t.milestone == milestone]
    if status:
        rows = [t for t in rows if t.status == status]
    if ready:
        rows = [t for t in rows if t.id in ready_ids]
    if blocked:
        blocked_ids = {t.id for t in blocked_tasks(manifest)}
        rows = [t for t in rows if t.id in blocked_ids]

    if json_mode:
        out.result({"tasks": [{**t.model_dump(), "ready": t.id in ready_ids} for t in rows]})
        return

    if not rows:
        out.result(None, human_text="(no tasks)")
        return

    # Group rows by milestone for a tidier table.
    by_milestone: dict[str, list] = {}
    for t in rows:
        by_milestone.setdefault(t.milestone, []).append(t)

    table = Table()
    table.add_column("Milestone")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Ready")
    table.add_column("Deps")
    table.add_column("Title")
    for m_id in sorted(by_milestone):
        for t in by_milestone[m_id]:
            table.add_row(
                m_id,
                t.id,
                t.status,
                "y" if t.id in ready_ids else "",
                ",".join(t.depends_on),
                t.title,
            )
    out.print_rich(table)
