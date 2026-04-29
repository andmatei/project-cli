"""`keel code rm`."""
from __future__ import annotations

import typer

from keel import git_ops, workspace
from keel.manifest import (
    DeliverableManifest,
    ProjectManifest,
    load_deliverable_manifest,
    load_project_manifest,
    save_deliverable_manifest,
    save_project_manifest,
)
from keel.output import Output
from keel.prompts import confirm_destructive


def cmd_rm(
    ctx: typer.Context,
    project: str | None = typer.Option(None, "--project", "-p", help="Project name. Auto-detected from CWD if omitted."),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable", help="Remove from deliverable scope."),
    repo: str = typer.Option(..., "--repo", "-r", help="Remote URL of the repo to remove."),
    force: bool = typer.Option(False, "--force", help="Allow removal even if the worktree has uncommitted changes."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print intended operations and exit; write nothing."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Remove a repo from the manifest and remove its worktree."""
    out = Output.from_context(ctx, json_mode=json_mode)
    scope = workspace.resolve_cli_scope(project, deliverable)
    project = scope.project
    deliverable = scope.deliverable

    if deliverable:
        manifest_path = workspace.deliverable_dir(project, deliverable) / "design" / "deliverable.toml"
        m: DeliverableManifest = load_deliverable_manifest(manifest_path)
    else:
        manifest_path = workspace.project_dir(project) / "design" / "project.toml"
        m: ProjectManifest = load_project_manifest(manifest_path)

    target = next((r for r in m.repos if r.remote == repo), None)
    if target is None:
        out.error(f"no repo with remote: {repo}", code="not_found")
        raise typer.Exit(code=1)

    unit_dir = manifest_path.parent.parent
    wt_path = unit_dir / target.worktree

    if dry_run:
        from keel.dryrun import OpLog
        log = OpLog()
        log.modify_file(manifest_path, diff=f"- [[repos]] remote={repo}")
        if wt_path.is_dir():
            log.remove_worktree(wt_path)
        out.info(log.format_summary())
        return

    confirm_destructive(
        f"Remove repo {repo} and its worktree at {wt_path}?",
        yes=yes,
    )

    # Remove worktree first; if dirty and not --force, abort before manifest mutation
    if wt_path.is_dir():
        try:
            git_ops.remove_worktree(wt_path, force=force)
        except git_ops.GitError as e:
            out.error(f"worktree removal failed (use --force if dirty): {e}", code="git_failed")
            raise typer.Exit(code=1) from None

    # Update manifest
    new_repos = [r for r in m.repos if r.remote != repo]
    if deliverable:
        new_m = DeliverableManifest(deliverable=m.deliverable, repos=new_repos)
        save_deliverable_manifest(manifest_path, new_m)
    else:
        new_m = ProjectManifest(project=m.project, repos=new_repos)
        save_project_manifest(manifest_path, new_m)

    out.info(f"Removed repo {repo}")
    out.result({"removed_remote": repo, "removed_worktree": str(wt_path)}, human_text=f"Removed: {repo}")
