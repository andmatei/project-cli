"""`keel task worktree <id>` — create a per-task git worktree at the task's branch."""

from __future__ import annotations

from pathlib import Path

import typer

from keel import git_ops
from keel.errors import ErrorCode
from keel.manifest import (
    DeliverableManifest,
    ProjectManifest,
    load_deliverable_manifest,
    load_milestones_manifest,
    load_project_manifest,
)
from keel.output import Output
from keel.workspace import resolve_cli_scope


def cmd_worktree(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    repo: str | None = typer.Option(
        None, "--repo", "-r",
        help="Worktree-dir name (from project manifest's [[repos]]). Required when project has multiple repos.",
    ),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Create a git worktree for a task at its recorded branch."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    manifest = load_milestones_manifest(scope.milestones_manifest_path)

    task = next((t for t in manifest.tasks if t.id == id), None)
    if task is None:
        out.error(f"no task with id '{id}'", code=ErrorCode.NOT_FOUND)
        raise typer.Exit(code=1)

    if not task.branch:
        out.error(
            f"task '{id}' has no branch recorded; run 'keel task start {id}' first",
            code=ErrorCode.INVALID_STATE,
        )
        raise typer.Exit(code=1)

    # Locate the project (or deliverable) manifest to get repos.
    if scope.deliverable:
        proj_manifest_path = scope.manifest_path
        deliv_m: DeliverableManifest = load_deliverable_manifest(proj_manifest_path)
        repos = deliv_m.repos
    else:
        proj_m: ProjectManifest = load_project_manifest(scope.manifest_path)
        repos = proj_m.repos

    if not repos:
        out.error(
            "no [[repos]] declared in the manifest; run 'keel code add' first",
            code=ErrorCode.NOT_FOUND,
        )
        raise typer.Exit(code=1)

    if repo is not None:
        target = next((r for r in repos if r.worktree == repo), None)
        if target is None:
            out.error(
                f"no repo with worktree dir '{repo}' found in manifest",
                code=ErrorCode.NOT_FOUND,
            )
            raise typer.Exit(code=1)
    elif len(repos) > 1:
        names = ", ".join(r.worktree for r in repos)
        out.error(
            f"project has multiple repos ({names}); use --repo NAME to choose one",
            code=ErrorCode.CONFLICTING_FLAGS,
        )
        raise typer.Exit(code=1)
    else:
        target = repos[0]

    # Compute destination path: <unit>/<worktree-dir>-<task-id>/
    unit_dir = scope.unit_dir
    dest = unit_dir / f"{target.worktree}-{task.id}"

    repo_path = Path(target.remote)
    try:
        git_ops.create_worktree(repo_path, dest, branch=task.branch)
    except git_ops.GitError as e:
        out.error(f"worktree creation failed: {e}", code=ErrorCode.GIT_FAILED)
        raise typer.Exit(code=1) from None

    out.result(
        {"task": id, "branch": task.branch, "worktree": str(dest)},
        human_text=f"Worktree created at {dest} (branch {task.branch})",
    )
