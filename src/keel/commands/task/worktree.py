"""`keel task worktree <id>` — create a per-task git worktree at the task's branch."""

from __future__ import annotations

from pathlib import Path

import typer

from keel import git_ops
from keel.api import (
    DeliverableManifest,
    ErrorCode,
    Output,
    ProjectManifest,
    find_task,
    load_deliverable_manifest,
    load_milestones_manifest,
    load_project_manifest,
    resolve_cli_scope,
)


def cmd_worktree(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(
        None,
        "-D",
        "--deliverable",
        help="Scope: a deliverable instead of the project. Auto-detected from CWD.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Project name. Auto-detected from CWD if omitted.",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        "-r",
        help="Worktree-dir name (from project manifest's [[repos]]). Required when project has multiple repos.",
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Create a git worktree for a task at its recorded branch."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    manifest = load_milestones_manifest(scope.milestones_manifest_path)

    task = find_task(manifest, id)
    if task is None:
        out.fail(f"no task with id '{id}'", code=ErrorCode.NOT_FOUND)

    if not task.branch:
        out.fail(
            f"task '{id}' has no branch recorded; run 'keel task start {id}' first",
            code=ErrorCode.INVALID_STATE,
        )

    # Locate the project (or deliverable) manifest to get repos.
    if scope.deliverable:
        proj_manifest_path = scope.manifest_path
        deliv_m: DeliverableManifest = load_deliverable_manifest(proj_manifest_path)
        repos = deliv_m.repos
    else:
        proj_m: ProjectManifest = load_project_manifest(scope.manifest_path)
        repos = proj_m.repos

    if not repos:
        out.fail(
            "no [[repos]] declared in the manifest; run 'keel code add' first",
            code=ErrorCode.NOT_FOUND,
        )

    if repo is not None:
        target = next((r for r in repos if r.worktree == repo), None)
        if target is None:
            out.fail(
                f"no repo with worktree dir '{repo}' found in manifest",
                code=ErrorCode.NOT_FOUND,
            )
    elif len(repos) > 1:
        names = ", ".join(r.worktree for r in repos)
        out.fail(
            f"project has multiple repos ({names}); use --repo NAME to choose one",
            code=ErrorCode.CONFLICTING_FLAGS,
            exit_code=2,
        )
    else:
        target = repos[0]

    # Compute destination path: <unit>/<worktree-dir>-<task-id>/
    unit_dir = scope.unit_dir
    dest = unit_dir / f"{target.worktree}-{task.id}"

    repo_path = Path(target.remote)
    try:
        git_ops.create_worktree(repo_path, dest, branch=task.branch)
    except git_ops.GitError as e:
        out.fail(f"worktree creation failed: {e}", code=ErrorCode.GIT_FAILED)

    out.result(
        {"task": id, "branch": task.branch, "worktree": str(dest)},
        human_text=f"Worktree created at {dest} (branch {task.branch})",
    )
