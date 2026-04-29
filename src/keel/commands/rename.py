"""`keel rename` (project-level)."""
from __future__ import annotations

import shutil

import typer

from keel import git_ops, workspace
from keel.manifest import (
    ProjectManifest,
    ProjectMeta,
    RepoSpec,
    load_project_manifest,
    save_project_manifest,
)
from keel.output import Output
from keel.prompts import confirm_destructive
from keel.util import slugify


def cmd_rename(
    ctx: typer.Context,
    old: str = typer.Argument(..., help="Current project name."),
    new: str = typer.Argument(..., help="New project name (will be slugified)."),
    rename_branches: bool = typer.Option(True, "--rename-branches/--no-rename-branches", help="Rename worktree branches to use the new project's branch_prefix."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print intended operations and exit; write nothing."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Rename a project — directory, worktrees, branch prefixes, deliverable references."""
    out = Output.from_context(ctx, json_mode=json_mode)
    new_slug = slugify(new)
    if not new_slug:
        out.error("invalid new project name", code="invalid_name")
        raise typer.Exit(code=2)

    if not workspace.project_exists(old):
        from keel.errors import HINT_LIST_PROJECTS
        out.error(f"project not found: {old}\n  {HINT_LIST_PROJECTS}", code="not_found")
        raise typer.Exit(code=1)
    if workspace.project_exists(new_slug):
        out.error(f"target project already exists: {new_slug}", code="exists")
        raise typer.Exit(code=1)

    old_path = workspace.project_dir(old)
    new_path = workspace.project_dir(new_slug)

    if dry_run:
        from keel.dryrun import OpLog
        log = OpLog()
        log.modify_file(old_path, diff=f"rename → {new_path}")
        out.info(log.format_summary())
        return

    confirm_destructive(
        f"Rename project {old} → {new_slug}? Worktrees and branches will move.",
        yes=yes,
    )

    m = load_project_manifest(workspace.manifest_path(old))

    # Move worktrees with git_ops.move_worktree (preserves linkage)
    branch_renames: list[tuple[str, str]] = []
    new_repos = []
    for r in m.repos:
        old_wt = old_path / r.worktree
        new_wt = new_path / r.worktree
        new_path.mkdir(parents=True, exist_ok=True)
        if old_wt.is_dir():
            git_ops.move_worktree(old_wt, new_wt)
            if rename_branches and r.branch_prefix and old in r.branch_prefix:
                old_branch = git_ops.current_branch(new_wt)
                if old_branch and old_branch.startswith(r.branch_prefix):
                    new_branch_prefix = r.branch_prefix.replace(old, new_slug, 1)
                    new_branch = old_branch.replace(r.branch_prefix, new_branch_prefix, 1)
                    git_ops.rename_branch(new_wt, old=old_branch, new=new_branch)
                    branch_renames.append((old_branch, new_branch))
                    r = RepoSpec(
                        remote=r.remote, local_hint=r.local_hint,
                        worktree=r.worktree, branch_prefix=new_branch_prefix,
                    )
        new_repos.append(r)

    # Move the rest (design dir, deliverables, etc.)
    for child in list(old_path.iterdir()):
        if (new_path / child.name).exists():
            continue  # already moved (worktree)
        shutil.move(str(child), str(new_path / child.name))

    # rmdir old path if empty
    if old_path.exists() and not any(old_path.iterdir()):
        old_path.rmdir()

    # Update manifest's name and (if renamed) repo branch prefixes
    new_manifest = ProjectManifest(
        project=ProjectMeta(
            name=new_slug,
            description=m.project.description,
            created=m.project.created,
        ),
        repos=new_repos,
    )
    save_project_manifest(workspace.manifest_path(new_slug), new_manifest)

    out.info(f"Renamed {old} → {new_slug}")
    out.result(
        {"old": old, "new": new_slug, "branch_renames": branch_renames},
        human_text=f"Renamed {old} → {new_slug} (branches: {len(branch_renames)}).",
    )
