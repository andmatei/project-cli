"""`keel milestone list`."""

from __future__ import annotations

import typer
from rich.table import Table

from keel.api import Output, load_milestones_manifest, resolve_cli_scope


def cmd_list(
    ctx: typer.Context,
    deliverable: str | None = typer.Option(
        None, "-D", "--deliverable", help="Scope: a deliverable. Auto-detected from CWD."
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Project name. Auto-detected from CWD if omitted."
    ),
    status: str | None = typer.Option(
        None, "--status", help="Filter by status (planned/active/done/cancelled)."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
) -> None:
    """List milestones at the current scope."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    manifest = load_milestones_manifest(scope.milestones_manifest_path)

    rows = list(manifest.milestones)
    if status:
        rows = [m for m in rows if m.status == status]

    if json_mode:
        out.result({"milestones": [m.model_dump() for m in rows]})
        return

    if not rows:
        out.result(None, human_text="(no milestones)")
        return

    table = Table()
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Title")
    table.add_column("Tasks")
    for m in rows:
        # count tasks belonging to this milestone (none yet at task implementation time;
        # will populate once Task commands land)
        task_count = sum(1 for t in manifest.tasks if t.milestone == m.id)
        table.add_row(m.id, m.status, m.title, str(task_count))
    out.print_rich(table)
