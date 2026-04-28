"""`keel deliverable rename <old> <new>`."""
from __future__ import annotations
import shutil
import typer

from keel import workspace
from keel.markdown_edit import insert_under_heading
from keel.manifest import (
    DeliverableManifest, DeliverableMeta,
    load_deliverable_manifest, save_deliverable_manifest,
)
from keel.output import Output


def cmd_rename(
    old: str = typer.Argument(...),
    new: str = typer.Argument(...),
    project: str | None = typer.Option(None, "--project", "-p"),
    rename_branch: bool = typer.Option(True, "--rename-branch/--no-rename-branch"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Rename a deliverable."""
    out = Output(json_mode=json_mode)

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
    manifest_path = new_path / "design" / "deliverable.toml"
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
    parent_claude = workspace.project_dir(project) / "design" / "CLAUDE.md"
    if parent_claude.is_file():
        text = parent_claude.read_text()
        new_lines = []
        for line in text.splitlines(keepends=True):
            if line.lstrip().startswith(f"- **{old}**:"):
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}- **{new}**: ../deliverables/{new}/design/ -- {description}\n")
            else:
                new_lines.append(line)
        parent_claude.write_text("".join(new_lines))

    parent_design = workspace.project_dir(project) / "design" / "design.md"
    if parent_design.is_file():
        text = parent_design.read_text()
        new_lines = []
        for line in text.splitlines(keepends=True):
            if line.lstrip().startswith(f"- **{old}**:"):
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(
                    f"{indent}- **{new}**: {description}. See [design](../deliverables/{new}/design/design.md).\n"
                )
            else:
                new_lines.append(line)
        parent_design.write_text("".join(new_lines))

    # 4. Update sibling deliverable CLAUDE.md files
    siblings_dir = workspace.project_dir(project) / "deliverables"
    if siblings_dir.is_dir():
        for sibling in siblings_dir.iterdir():
            if not sibling.is_dir() or sibling.name == new:
                continue
            sibling_claude = sibling / "design" / "CLAUDE.md"
            if sibling_claude.is_file():
                text = sibling_claude.read_text()
                new_lines = []
                for line in text.splitlines(keepends=True):
                    if line.lstrip().startswith(f"- {old}:"):
                        indent = line[:len(line) - len(line.lstrip())]
                        new_lines.append(f"{indent}- {new}: ../{new}/design/ -- {description}\n")
                    else:
                        new_lines.append(line)
                sibling_claude.write_text("".join(new_lines))

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
