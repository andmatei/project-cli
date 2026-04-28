"""`keel deliverable list`."""
from __future__ import annotations
from dataclasses import dataclass
import typer
from rich.table import Table

from keel import workspace
from keel.manifest import load_deliverable_manifest
from keel.output import Output


@dataclass
class _DeliverableRow:
    name: str
    phase: str
    description: str
    shared_worktree: bool


def _scan(project_name: str) -> list[_DeliverableRow]:
    rows: list[_DeliverableRow] = []
    deliv_dir = workspace.project_dir(project_name) / "deliverables"
    if not deliv_dir.is_dir():
        return rows
    for child in sorted(deliv_dir.iterdir()):
        manifest_path = child / "design" / "deliverable.toml"
        if not manifest_path.is_file():
            continue
        m = load_deliverable_manifest(manifest_path)
        phase_file = child / "design" / ".phase"
        phase = phase_file.read_text().splitlines()[0].strip() if phase_file.is_file() else "scoping"
        rows.append(_DeliverableRow(
            name=m.deliverable.name,
            phase=phase,
            description=m.deliverable.description,
            shared_worktree=m.deliverable.shared_worktree,
        ))
    return rows


def cmd_list(
    project: str | None = typer.Option(None, "--project", "-p"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """List deliverables in a project."""
    out = Output(json_mode=json_mode)
    from keel.workspace import resolve_cli_scope
    scope = resolve_cli_scope(project, None, allow_deliverable=False)
    project = scope.project

    rows = _scan(project)

    if json_mode:
        out.result({
            "deliverables": [
                {"name": r.name, "phase": r.phase, "description": r.description,
                 "shared_worktree": r.shared_worktree}
                for r in rows
            ]
        })
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
