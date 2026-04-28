"""`keel deliverable rm <name>`."""
from __future__ import annotations
import shutil
import typer

from keel import workspace
from keel.markdown_edit import remove_line_under_heading
from keel.output import Output
from keel.prompts import confirm_destructive


def cmd_rm(
    name: str = typer.Argument(...),
    project: str | None = typer.Option(None, "--project", "-p"),
    keep_code: bool = typer.Option(False, "--keep-code"),
    keep_design: bool = typer.Option(False, "--keep-design"),
    force: bool = typer.Option(False, "--force", help="Allow even if worktree is dirty."),
    yes: bool = typer.Option(False, "-y", "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Remove a deliverable, including its design dir, worktree, and parent references."""
    out = Output(json_mode=json_mode)

    if project is None:
        scope = workspace.detect_scope()
        project = scope.project
    if project is None:
        out.error("no project specified and none detected from CWD", code="no_project")
        raise typer.Exit(code=1)
    if not workspace.deliverable_exists(project, name):
        out.error(f"deliverable not found: {project}/{name}", code="not_found")
        raise typer.Exit(code=1)

    deliv = workspace.deliverable_dir(project, name)

    if dry_run:
        from keel.dryrun import OpLog
        log = OpLog()
        if not keep_design:
            log.delete_file(deliv)
        log.modify_file(
            workspace.project_dir(project) / "design" / "CLAUDE.md",
            diff=f"- - **{name}**: ...",
        )
        log.modify_file(
            workspace.project_dir(project) / "design" / "design.md",
            diff=f"- - **{name}**: ...",
        )
        out.info(log.format_summary())
        return

    confirm_destructive(
        f"Remove deliverable {project}/{name}? This deletes its design dir.",
        yes=yes,
    )

    # Remove design dir
    if not keep_design:
        shutil.rmtree(deliv)

    # Clean up parent CLAUDE.md
    parent_claude = workspace.project_dir(project) / "design" / "CLAUDE.md"
    if parent_claude.is_file():
        # Match the format used by `deliverable add`: `- **{name}**: ...`
        text = parent_claude.read_text()
        # Find the line(s) starting with the deliverable bullet and remove them
        new_lines = [
            line for line in text.splitlines(keepends=True)
            if not line.lstrip().startswith(f"- **{name}**:")
        ]
        parent_claude.write_text("".join(new_lines))

    # Clean up parent design.md
    parent_design = workspace.project_dir(project) / "design" / "design.md"
    if parent_design.is_file():
        text = parent_design.read_text()
        new_lines = [
            line for line in text.splitlines(keepends=True)
            if not line.lstrip().startswith(f"- **{name}**:")
        ]
        parent_design.write_text("".join(new_lines))

    # Clean up sibling deliverable CLAUDE.md files
    siblings_dir = workspace.project_dir(project) / "deliverables"
    if siblings_dir.is_dir():
        for sibling in siblings_dir.iterdir():
            if not sibling.is_dir():
                continue
            sibling_claude = sibling / "design" / "CLAUDE.md"
            if sibling_claude.is_file():
                text = sibling_claude.read_text()
                # Sibling lines look like: `- {name}: ../{name}/design/ -- description`
                new_lines = [
                    line for line in text.splitlines(keepends=True)
                    if not line.lstrip().startswith(f"- {name}:")
                ]
                sibling_claude.write_text("".join(new_lines))

    out.info(f"Removed deliverable: {deliv}")
    out.result({"removed": str(deliv)}, human_text=f"Deliverable removed: {deliv}")
