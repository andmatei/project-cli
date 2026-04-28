"""`keel deliverable add <name>`."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import re
import typer

from keel import templates, workspace
from keel.manifest import (
    DeliverableManifest, DeliverableMeta,
    save_deliverable_manifest,
)
from keel.output import Output
from keel.prompts import require_or_fail


_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(name: str) -> str:
    s = name.lower().strip().replace(" ", "-")
    return _SLUG_RE.sub("", s)


def cmd_add(
    name: str = typer.Argument(..., help="Deliverable name (will be slugified)."),
    description: str | None = typer.Option(None, "-d", "--description"),
    project: str | None = typer.Option(None, "--project", "-p", help="Parent project (auto-detected from CWD)."),
    repo: str | None = typer.Option(None, "-r", "--repo", help="Source repo for the deliverable's worktree."),
    shared: bool = typer.Option(False, "--shared", help="Share parent's worktree (no own [[repos]])."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Create a new deliverable inside a project."""
    out = Output(json_mode=json_mode)

    # Determine parent project: explicit --project overrides; else CWD-detect; else fail.
    if project is None:
        scope = workspace.detect_scope()
        project = scope.project
    if project is None:
        out.error("no parent project specified and none detected from CWD", code="no_project")
        raise typer.Exit(code=1)
    if not workspace.project_exists(project):
        out.error(f"parent project not found: {project}", code="not_found")
        raise typer.Exit(code=1)

    slug = _slugify(name)
    if not slug:
        out.error("invalid deliverable name", code="invalid_name")
        raise typer.Exit(code=2)

    deliv = workspace.deliverable_dir(project, slug)
    if deliv.exists():
        out.error(f"deliverable already exists: {deliv}", code="exists")
        raise typer.Exit(code=1)

    description = require_or_fail(description, arg_name="--description", label="Description")

    if dry_run:
        from keel.dryrun import OpLog
        log = OpLog()
        log.create_file(deliv / "design" / "deliverable.toml", size=0)
        log.create_file(deliv / "design" / "CLAUDE.md", size=0)
        log.create_file(deliv / "design" / "design.md", size=0)
        log.create_file(deliv / "design" / ".phase", size=0)
        today = date.today().isoformat()
        log.create_file(deliv / "design" / "decisions" / f"{today}-deliverable-created.md", size=0)
        out.info(log.format_summary())
        return

    # Create directories
    (deliv / "design" / "decisions").mkdir(parents=True)

    # Manifest
    manifest = DeliverableManifest(
        deliverable=DeliverableMeta(
            name=slug,
            parent_project=project,
            description=description,
            created=date.today(),
            shared_worktree=shared,
        ),
        repos=[],
    )
    save_deliverable_manifest(deliv / "design" / "deliverable.toml", manifest)

    # Templates
    (deliv / "design" / "CLAUDE.md").write_text(
        templates.render("claude_md.j2", name=slug, description=description, repos=[], deliverables=[])
    )
    (deliv / "design" / "design.md").write_text(
        templates.render("design_md.j2", name=slug, description=description)
    )

    # Phase
    (deliv / "design" / ".phase").write_text("scoping\n")

    # Initial decision
    today = date.today().isoformat()
    (deliv / "design" / "decisions" / f"{today}-deliverable-created.md").write_text(
        templates.render("decision_entry.j2", date=today, title=f"Create deliverable {slug}")
    )

    out.info(f"Created deliverable: {deliv}")

    # AST-edit the parent's CLAUDE.md to list this deliverable
    from keel.markdown_edit import insert_under_heading
    parent_claude_path = workspace.project_dir(project) / "design" / "CLAUDE.md"
    if parent_claude_path.is_file():
        line = f"- **{slug}**: ../deliverables/{slug}/design/ -- {description}\n"
        new_text = insert_under_heading(parent_claude_path.read_text(), "Deliverables", line)
        parent_claude_path.write_text(new_text)

    # AST-edit the parent's design.md
    parent_design_path = workspace.project_dir(project) / "design" / "design.md"
    if parent_design_path.is_file():
        line = f"- **{slug}**: {description}. See [design](../deliverables/{slug}/design/design.md).\n"
        new_text = insert_under_heading(parent_design_path.read_text(), "Deliverables", line)
        parent_design_path.write_text(new_text)

    modified_files = []
    if parent_claude_path.is_file():
        modified_files.append(str(parent_claude_path))
    if parent_design_path.is_file():
        modified_files.append(str(parent_design_path))
    out.result(
        {"deliverable_path": str(deliv), "modified_files": modified_files},
        human_text=f"Deliverable created: {deliv}",
    )
