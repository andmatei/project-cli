"""`keel migrate` — convert legacy Bash CLI projects to manifest format."""
from __future__ import annotations

import typer

from keel import workspace
from keel.output import Output


def cmd_migrate(
    ctx: typer.Context,
    name: str | None = typer.Argument(None, help="Project name to migrate. Auto-detected from CWD if omitted."),
    all_projects: bool = typer.Option(False, "--all", help="Migrate every legacy project under $PROJECTS_DIR."),
    apply: bool = typer.Option(False, "--apply", help="Actually write the manifests (default is dry-run preview)."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Migrate a project (or all projects) from Bash-CLI format to manifest format.

    Default is dry-run; pass --apply to write.
    """
    out = Output.from_context(ctx, json_mode=json_mode)

    if all_projects:
        targets = []
        root = workspace.projects_dir()
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if child.is_dir() and (child / "design" / "CLAUDE.md").is_file():
                    targets.append(child.name)
    else:
        if name is None:
            scope = workspace.detect_scope()
            name = scope.project
        if name is None:
            out.error("no project specified and none detected from CWD", code="no_project")
            raise typer.Exit(code=1)
        if not (workspace.project_dir(name) / "design" / "CLAUDE.md").is_file():
            out.error(f"not a project: {name}", code="not_found")
            raise typer.Exit(code=1)
        targets = [name]

    results: list[dict] = []
    for target in targets:
        proj_dir = workspace.project_dir(target)
        if (proj_dir / "design" / "project.toml").is_file():
            out.info(f"{target}: already migrated, skipping")
            results.append({"name": target, "status": "skipped"})
            continue
        # Dry-run-only path for T1.1; T1.2-T1.6 implement the actual migration.
        out.info(f"[dry-run] would migrate {target}")
        results.append({"name": target, "status": "dry-run"})

    out.result({"results": results}, human_text=f"Processed {len(results)} project(s).")
