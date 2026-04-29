"""`keel deliverable rename <old> <new>`."""

from __future__ import annotations

import shutil

import typer

from keel import workspace
from keel.manifest import (
    DeliverableManifest,
    DeliverableMeta,
    load_deliverable_manifest,
    save_deliverable_manifest,
)
from keel.markdown_edit import insert_under_heading, remove_bullet_under_heading
from keel.output import Output


def cmd_rename(
    ctx: typer.Context,
    old: str = typer.Argument(...),
    new: str = typer.Argument(...),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Parent project. Auto-detected from CWD if omitted."
    ),
    rename_branch: bool = typer.Option(
        True,
        "--rename-branch/--no-rename-branch",
        help="Also rename the worktree's git branch (default true).",
    ),
    yes: bool = typer.Option(
        False, "-y", "--yes", help="Skip interactive prompts (description, etc.)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Rename a deliverable."""
    out = Output.from_context(ctx, json_mode=json_mode)

    from keel.workspace import resolve_cli_scope

    scope = resolve_cli_scope(project, None, allow_deliverable=False)
    project = scope.project
    if not workspace.deliverable_exists(project, old):
        out.error(f"deliverable not found: {project}/{old}", code="not_found")
        raise typer.Exit(code=1)
    if workspace.deliverable_exists(project, new):
        out.error(f"target already exists: {project}/{new}", code="exists")
        raise typer.Exit(code=1)

    old_path = workspace.deliverable_dir(project, old)
    new_path = workspace.deliverable_dir(project, new)

    if dry_run:
        from keel.dryrun import OpLog

        log = OpLog()
        log.modify_file(old_path, diff=f"rename → {new_path}")
        out.info(log.format_summary())
        return

    # 1a. If a worktree exists, move it properly via git first
    old_code = old_path / "code"
    if old_code.is_dir():
        from keel import git_ops

        new_path.mkdir(parents=True, exist_ok=True)
        git_ops.move_worktree(old_code, new_path / "code")

    # 1b. Move the design dir (and any other contents)
    new_path.mkdir(parents=True, exist_ok=True)
    for child in list(old_path.iterdir()):
        shutil.move(str(child), str(new_path / child.name))

    # 1c. rmdir the now-empty old path
    if old_path.exists() and not any(old_path.iterdir()):
        old_path.rmdir()

    # 2. Update manifest's `name`
    manifest_path = workspace.manifest_path(project, new)
    m = load_deliverable_manifest(manifest_path)
    new_manifest = DeliverableManifest(
        deliverable=DeliverableMeta(
            name=new,
            parent_project=m.deliverable.parent_project,
            description=m.deliverable.description,
            created=m.deliverable.created,
            shared_worktree=m.deliverable.shared_worktree,
        ),
        repos=m.repos,
    )
    save_deliverable_manifest(manifest_path, new_manifest)

    # 3. Update parent CLAUDE.md and design.md references
    description = m.deliverable.description
    parent_claude = workspace.design_dir(project) / "CLAUDE.md"
    if parent_claude.is_file():
        text = remove_bullet_under_heading(
            parent_claude.read_text(), "Deliverables", f"- **{old}**:"
        )
        text = insert_under_heading(
            text, "Deliverables", f"- **{new}**: ../deliverables/{new}/design/ -- {description}\n"
        )
        parent_claude.write_text(text)

    parent_design = workspace.design_dir(project) / "design.md"
    if parent_design.is_file():
        text = remove_bullet_under_heading(
            parent_design.read_text(), "Deliverables", f"- **{old}**:"
        )
        text = insert_under_heading(
            text,
            "Deliverables",
            f"- **{new}**: {description}. See [design](../deliverables/{new}/design/design.md).\n",
        )
        parent_design.write_text(text)

    # 4. Update sibling deliverable CLAUDE.md files
    siblings_dir = workspace.project_dir(project) / "deliverables"
    if siblings_dir.is_dir():
        for sibling in siblings_dir.iterdir():
            if not sibling.is_dir() or sibling.name == new:
                continue
            sibling_claude = sibling / "design" / "CLAUDE.md"
            if sibling_claude.is_file():
                text = remove_bullet_under_heading(
                    sibling_claude.read_text(), "Sibling deliverables", f"- {old}:"
                )
                text = insert_under_heading(
                    text, "Sibling deliverables", f"- {new}: ../{new}/design/ -- {description}\n"
                )
                sibling_claude.write_text(text)

    # 5. (Optional) branch rename
    code_dir = new_path / "code"
    if code_dir.is_dir() and rename_branch and m.repos:
        from keel import git_ops

        old_branch = m.repos[0].branch_prefix
        if old_branch and old_branch.endswith(f"-{old}"):
            new_branch = old_branch[: -len(f"-{old}")] + f"-{new}"
            try:
                git_ops.rename_branch(code_dir, old=old_branch, new=new_branch)
            except git_ops.GitError as e:
                out.warn(f"branch rename failed: {e}")

    out.info(f"Renamed {old} → {new}")
    out.result(
        {"old": str(old_path), "new": str(new_path)},
        human_text=f"Deliverable renamed: {old} → {new}",
    )
