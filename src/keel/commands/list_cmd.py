"""`keel list`."""
from __future__ import annotations
from dataclasses import dataclass
import typer
from rich.tree import Tree

from keel import workspace
from keel.manifest import load_project_manifest
from keel.output import Output


@dataclass
class _ProjectRow:
    name: str
    phase: str
    description: str
    deliverable_count: int


def _scan(projects_root) -> list[_ProjectRow]:
    rows: list[_ProjectRow] = []
    if not projects_root.exists():
        return rows
    for child in sorted(projects_root.iterdir()):
        design = child / "design"
        manifest = design / "project.toml"
        if not manifest.is_file():
            continue
        m = load_project_manifest(manifest)
        phase_file = design / ".phase"
        phase = phase_file.read_text().splitlines()[0].strip() if phase_file.is_file() else "scoping"
        d_dir = child / "deliverables"
        d_count = 0
        if d_dir.is_dir():
            d_count = sum(1 for d in d_dir.iterdir() if (d / "design" / "deliverable.toml").is_file())
        rows.append(_ProjectRow(
            name=m.project.name,
            phase=phase,
            description=m.project.description,
            deliverable_count=d_count,
        ))
    return rows


def cmd_list(
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase."),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """List projects in the workspace."""
    out = Output(json_mode=json_mode)
    rows = _scan(workspace.projects_dir())
    total = len(rows)
    if phase:
        rows = [r for r in rows if r.phase == phase]

    if json_mode:
        out.result({
            "projects": [
                {"name": r.name, "phase": r.phase, "description": r.description,
                 "deliverable_count": r.deliverable_count}
                for r in rows
            ]
        })
        return

    if not rows:
        if phase is not None and total > 0:
            out.result(None, human_text=f"(no projects in phase {phase!r})")
        else:
            out.result(None, human_text="(no projects)")
        return

    tree = Tree("Projects")
    for r in rows:
        label = f"[bold]{r.name}[/bold]  \\[{r.phase}]"
        if r.deliverable_count:
            label += f"  ({r.deliverable_count} deliverable{'s' if r.deliverable_count != 1 else ''})"
        tree.add(label)
    out.print_rich(tree)
