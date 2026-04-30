"""`keel show`."""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from keel import workspace
from keel.api import Output, load_project_manifest
from keel.workspace import resolve_cli_scope


def cmd_show(
    ctx: typer.Context,
    name: str | None = typer.Argument(
        None, help="Project name. Auto-detected from CWD if omitted."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Show a project's structure and current state."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(name, None, allow_deliverable=False, out=out)
    name = scope.project

    proj = workspace.project_dir(name)

    m = load_project_manifest(scope.manifest_path)
    phase = workspace.read_phase(scope.design_dir)
    decisions = sorted(scope.decisions_dir.glob("*.md"))
    decision_count = len(decisions)

    deliverables: list[tuple[str, str]] = []
    d_dir = proj / "deliverables"
    if d_dir.is_dir():
        for d in sorted(d_dir.iterdir()):
            d_manifest = d / "design" / "deliverable.toml"
            if d_manifest.is_file():
                d_phase = workspace.read_phase(d / "design")
                deliverables.append((d.name, d_phase))

    if json_mode:
        out.result(
            {
                "name": m.project.name,
                "description": m.project.description,
                "path": str(proj),
                "phase": phase,
                "repos": [r.model_dump() for r in m.repos],
                "decision_count": decision_count,
                "deliverables": [{"name": n, "phase": p} for n, p in deliverables],
            }
        )
        return

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("Name", m.project.name)
    table.add_row("Description", m.project.description)
    table.add_row("Path", str(proj))
    table.add_row("Phase", phase)
    table.add_row("Decisions", str(decision_count))
    if m.repos:
        table.add_row("Repos", "\n".join(f"{r.worktree}/  ←  {r.remote}" for r in m.repos))
    if deliverables:
        table.add_row("Deliverables", "\n".join(f"{n}  [{p}]" for n, p in deliverables))
    out.print_rich(Panel(table, title=f"Project: {m.project.name}", border_style="blue"))
