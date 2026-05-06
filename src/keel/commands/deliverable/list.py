"""`keel deliverable list`."""

from __future__ import annotations

from dataclasses import dataclass

import typer
from rich.table import Table

from keel import workspace
from keel.api import Output, load_project_manifest, resolve_cli_scope


@dataclass
class _DeliverableRow:
    name: str
    phase: str
    description: str
    shared_worktree: bool


def _scan(project_name: str) -> list[_DeliverableRow]:
    rows: list[_DeliverableRow] = []
    project_scope = workspace.Scope(project=project_name)
    deliv_dir = project_scope.unit_dir / "deliverables"
    if not deliv_dir.is_dir():
        return rows
    for child in sorted(deliv_dir.iterdir()):
        deliv_scope = workspace.Scope(project=project_name, deliverable=child.name)
        manifest_path = deliv_scope.manifest_path
        if not manifest_path.is_file():
            continue
        m = load_project_manifest(manifest_path)
        phase = workspace.read_phase(deliv_scope.unit_dir)
        rows.append(
            _DeliverableRow(
                name=m.project.name,
                phase=phase,
                description=m.project.description,
                shared_worktree=m.project.shared_worktree,
            )
        )
    return rows


def cmd_list(
    ctx: typer.Context,
    project: str | None = typer.Option(
        None, "--project", "-p", help="Parent project. Auto-detected from CWD if omitted."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """List deliverables in a project."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, None, allow_deliverable=False, out=out)
    project = scope.project

    rows = _scan(project)

    if json_mode:
        out.result(
            {
                "deliverables": [
                    {
                        "name": r.name,
                        "phase": r.phase,
                        "description": r.description,
                        "shared_worktree": r.shared_worktree,
                    }
                    for r in rows
                ]
            }
        )
        return

    if not rows:
        out.result(None, human_text="(no deliverables)")
        return

    table = Table(title=f"Deliverables of {project}")
    table.add_column("Name")
    table.add_column("Phase")
    table.add_column("Shared")
    table.add_column("Description")
    for r in rows:
        table.add_row(r.name, r.phase, "yes" if r.shared_worktree else "no", r.description)
    out.print_rich(table)
