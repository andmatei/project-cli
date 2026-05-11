"""`keel hooks init [--project NAME]`."""

from __future__ import annotations

import typer

from keel import templates, workspace
from keel.api import Output


def cmd_init(
    ctx: typer.Context,
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="If set, scaffold the project's .keel/hooks/. Otherwise: the workspace's.",
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Scaffold a .keel/hooks/ directory (workspace-global or project-local)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    if project is None:
        target = workspace.projects_dir() / ".keel" / "hooks"
    else:
        target = workspace.project_dir(project) / ".keel" / "hooks"

    target.mkdir(parents=True, exist_ok=True)
    readme = target / "README.md"
    if not readme.is_file():
        readme.write_text(templates.render("hooks_readme.md.j2"))

    out.result(
        {"hooks_dir": str(target)},
        human_text=f"Hooks dir ready: {target}",
    )
