"""`keel decision new <title>`."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import os
import re
import subprocess
import typer

from keel import templates, workspace
from keel.output import Output
from keel.util import slugify


def cmd_new(
    title: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    slug: str | None = typer.Option(None, "--slug"),
    supersedes: str | None = typer.Option(None, "--supersedes"),
    no_edit: bool = typer.Option(False, "--no-edit"),
    force: bool = typer.Option(False, "--force"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Create a new decision record at the current scope (project or deliverable)."""
    out = Output(json_mode=json_mode)

    # Resolve scope
    if project is None or (deliverable is None and workspace.detect_scope().deliverable):
        scope = workspace.detect_scope()
        project = project or scope.project
        deliverable = deliverable if deliverable is not None else scope.deliverable
    if project is None:
        out.error("no project specified and none detected from CWD", code="no_project")
        raise typer.Exit(code=1)
    if not workspace.project_exists(project):
        out.error(f"project not found: {project}", code="not_found")
        raise typer.Exit(code=1)
    if deliverable is not None and not workspace.deliverable_exists(project, deliverable):
        out.error(f"deliverable not found: {project}/{deliverable}", code="not_found")
        raise typer.Exit(code=1)

    # Compute target dir
    if deliverable:
        target_dir = workspace.deliverable_dir(project, deliverable) / "design" / "decisions"
        scope_label = "deliverable"
    else:
        target_dir = workspace.project_dir(project) / "design" / "decisions"
        scope_label = "project"

    today = date.today().isoformat()
    slug_value = slug or slugify(title)
    if not slug_value:
        out.error("invalid title (slug is empty)", code="invalid_title")
        raise typer.Exit(code=2)
    filename = f"{today}-{slug_value}.md"
    path = target_dir / filename

    if path.exists() and not force:
        out.error(f"decision file already exists: {path}", code="exists")
        raise typer.Exit(code=1)

    # Validate --supersedes early, before creating the new file
    supersedes_path: Path | None = None
    if supersedes:
        candidate_paths = list(target_dir.glob(f"*-{supersedes}.md")) if not supersedes.endswith(".md") else [target_dir / supersedes]
        candidate_paths = [c for c in candidate_paths if c.is_file()]
        if not candidate_paths:
            out.error(
                f"--supersedes: no decision matching '{supersedes}' found in {target_dir}",
                code="not_found",
            )
            raise typer.Exit(code=1)
        supersedes_path = candidate_paths[0]

    if dry_run:
        from keel.dryrun import OpLog
        log = OpLog()
        log.create_file(path, size=0)
        out.info(log.format_summary())
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(templates.render("decision_entry.j2", date=today, title=title))

    if supersedes and supersedes_path is not None:
        # supersedes_path was validated above — apply the status mutation
        old_text = supersedes_path.read_text()
        # Replace status field in frontmatter
        new_text = re.sub(
            r"^status:\s*\S+",
            "status: superseded",
            old_text,
            count=1,
            flags=re.MULTILINE,
        )
        # Append "Superseded by:" line at end
        superseded_by_line = f"\nSuperseded by: {filename[:-3]}\n"  # strip .md
        if "Superseded by:" not in new_text:
            new_text = new_text.rstrip("\n") + superseded_by_line
        supersedes_path.write_text(new_text)

    out.info(f"Created decision: {path}")
    out.result(
        {"path": str(path), "scope": scope_label, "slug": slug_value, "supersedes": supersedes},
        human_text=f"Decision created: {path}",
    )

    # Open editor
    if not no_edit and os.environ.get("EDITOR") and not dry_run:
        try:
            subprocess.run([os.environ["EDITOR"], str(path)], check=False)
        except Exception:
            pass  # don't fail the command if editor invocation fails
