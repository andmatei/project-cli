"""`keel code add`."""
from __future__ import annotations

from pathlib import Path

import typer

from keel import git_ops, workspace
from keel.dryrun import OpLog
from keel.errors import ErrorCode
from keel.manifest import (
    DeliverableManifest,
    ProjectManifest,
    RepoSpec,
    load_deliverable_manifest,
    load_project_manifest,
    save_deliverable_manifest,
    save_project_manifest,
)
from keel.output import Output


def cmd_add(
    ctx: typer.Context,
    project: str | None = typer.Option(None, "--project", "-p", help="Project name. Auto-detected from CWD if omitted."),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable", help="Add the repo at deliverable scope."),
    repo: str = typer.Option(..., "--repo", "-r", help="Source git repo path."),
    worktree: str | None = typer.Option(None, "--worktree", help="Override the worktree dir name (default: derived from repo basename)."),
    branch_prefix: str | None = typer.Option(None, "--branch-prefix", help="Override the branch prefix."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip interactive prompts."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print intended operations and exit; write nothing."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Add a source repo to the manifest and create its worktree."""
    out = Output.from_context(ctx, json_mode=json_mode)
    scope = workspace.resolve_cli_scope(project, deliverable, out=out)
    project = scope.project
    deliverable = scope.deliverable

    repo_path = Path(repo).expanduser().resolve()
    if not git_ops.is_git_repo(repo_path):
        out.fail(f"not a git repo: {repo_path}", code=ErrorCode.NOT_A_REPO)

    # Decide worktree dir name — derived from repo basename, prefixed with "code-".
    # An explicit --worktree always wins.
    wt_name = worktree or f"code-{repo_path.name}"

    # Derive branch prefix if not supplied
    if branch_prefix is None:
        try:
            user_slug = git_ops.git_user_slug(repo_path)
        except Exception:
            user_slug = "user"
        suffix = f"-{deliverable}" if deliverable else ""
        branch_prefix = f"{user_slug}/{project}{suffix}-{repo_path.name}"

    # Load manifest
    if deliverable:
        manifest_path = workspace.deliverable_dir(project, deliverable) / "design" / "deliverable.toml"
        m: DeliverableManifest = load_deliverable_manifest(manifest_path)
    else:
        manifest_path = workspace.project_dir(project) / "design" / "project.toml"
        m: ProjectManifest = load_project_manifest(manifest_path)

    # Detect duplicates
    for existing in m.repos:
        if existing.remote == str(repo_path):
            out.fail(f"duplicate remote: {repo_path} already declared", code=ErrorCode.DUPLICATE_REMOTE)
        if existing.worktree == wt_name:
            out.fail(
                f"worktree name '{wt_name}' already in use. Pass --worktree NAME to disambiguate.",
                code=ErrorCode.DUPLICATE_WORKTREE,
            )

    new_spec = RepoSpec(
        remote=str(repo_path),
        local_hint=str(repo_path),
        worktree=wt_name,
        branch_prefix=branch_prefix,
    )

    if dry_run:
        log = OpLog()
        log.modify_file(manifest_path, diff=f"+ [[repos]] remote={repo_path} worktree={wt_name}")
        unit_dir = manifest_path.parent.parent
        log.create_worktree(unit_dir / wt_name, source=repo_path, branch=branch_prefix)
        out.info(log.format_summary())
        return

    # Append + write back
    new_repos = list(m.repos) + [new_spec]
    if deliverable:
        new_m = DeliverableManifest(deliverable=m.deliverable, repos=new_repos)
        save_deliverable_manifest(manifest_path, new_m)
    else:
        new_m = ProjectManifest(project=m.project, repos=new_repos)
        save_project_manifest(manifest_path, new_m)

    # Create worktree
    unit_dir = manifest_path.parent.parent
    try:
        git_ops.create_worktree(repo_path, unit_dir / wt_name, branch=branch_prefix)
    except git_ops.GitError as e:
        out.info("Manifest was updated; remove the new [[repos]] entry manually if you want to retry.")
        out.fail(f"worktree creation failed: {e}", code=ErrorCode.GIT_FAILED)

    out.info(f"Added repo {repo_path} → worktree {unit_dir / wt_name}")
    out.result(
        {"remote": str(repo_path), "worktree": str(unit_dir / wt_name), "branch_prefix": branch_prefix},
        human_text=f"Repo added: {repo_path}",
    )
