"""`keel new <name>`."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import typer

from keel import git_ops, templates, workspace
from keel.api import (
    ErrorCode,
    OpLog,
    Output,
    ProjectManifest,
    ProjectMeta,
    RepoSpec,
    require_or_fail,
    save_project_manifest,
    slugify,
)
from keel.lifecycles import (
    Lifecycle,
    LifecycleNotFoundError,
    lifecycle_source_path,
    load_lifecycle,
)


def cmd_new(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Project name (will be slugified)."),
    description: str | None = typer.Option(
        None,
        "-d",
        "--description",
        help="Brief project description; required (prompted on TTY if missing).",
    ),
    repos: list[str] | None = typer.Option(
        None,
        "-r",
        "--repo",
        help="Source git repo for a worktree. Repeatable for multi-repo projects.",
    ),
    no_worktree: bool = typer.Option(
        False, "--no-worktree", help="Skip worktree creation even if --repo provided."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    yes: bool = typer.Option(
        False, "-y", "--yes", help="Skip interactive prompts (description, etc.)."
    ),
    lifecycle: str = typer.Option(
        "default",
        "--lifecycle",
        help="Phase lifecycle to use for this project. See 'keel lifecycle list'.",
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Create a new project workspace."""
    out = Output.from_context(ctx, json_mode=json_mode)
    slug = slugify(name)
    if not slug:
        out.fail("invalid project name", code=ErrorCode.INVALID_NAME, exit_code=2)

    scope = workspace.Scope(project=slug, deliverable=None)
    proj = scope.unit_dir
    if proj.exists():
        out.fail(f"project already exists: {proj}", code=ErrorCode.EXISTS)

    description = require_or_fail(description, arg_name="--description", label="Description")

    # Validate and load the lifecycle
    try:
        lc = load_lifecycle(lifecycle)
    except LifecycleNotFoundError:
        out.fail(
            f"unknown lifecycle '{lifecycle}' (run 'keel lifecycle list' to see available options)",
            code=ErrorCode.NOT_FOUND,
        )

    # Resolve and validate repos up front
    repo_paths: list[Path] = []
    if repos and not no_worktree:
        for r in repos:
            rp = Path(r).expanduser().resolve()
            if not git_ops.is_git_repo(rp):
                out.fail(f"not a git repo: {rp}", code=ErrorCode.NOT_A_REPO)
            repo_paths.append(rp)

    # Build repo specs from validated paths.
    repo_specs = _build_repo_specs(slug, repo_paths)

    if dry_run:
        log = OpLog()
        log.create_file(scope.manifest_path, size=0)
        log.create_file(scope.readme_path, size=0)
        log.create_file(scope.scope_md_path, size=0)
        log.create_file(scope.design_md_path, size=0)
        log.create_file(scope.phase_path, size=0)
        log.create_file(scope.lifecycle_lock_path, size=0)
        for rp, spec in zip(repo_paths, repo_specs, strict=True):
            log.create_worktree(proj / spec.worktree, source=rp, branch=spec.branch_prefix)
        out.info(log.format_summary())
        return

    manifest = _scaffold_unit(
        scope=scope,
        name=slug,
        description=description,
        lifecycle=lifecycle,
        repos=repo_specs,
        lc=lc,
    )

    # Worktrees (last — file ops above already done)
    created_worktrees: list[str] = []
    for rp, spec in zip(repo_paths, manifest.repos, strict=True):
        wt_dest = proj / spec.worktree
        try:
            git_ops.create_worktree(rp, wt_dest, branch=spec.branch_prefix)
            created_worktrees.append(str(wt_dest))
        except git_ops.GitError as e:
            out.info(f"Files are at {proj}; clean up with `rm -rf {proj}` or retry.")
            out.fail(f"worktree creation failed: {e}", code=ErrorCode.GIT_FAILED)

    out.result(
        {"path": str(proj), "worktrees": created_worktrees},
        human_text=f"Project created: {proj}",
    )


def _build_repo_specs(slug: str, repo_paths: list[Path]) -> list[RepoSpec]:
    """Construct RepoSpec entries for each validated source repo path.

    Worktree path defaults to "code" when single, "code-<repo>" otherwise.
    """
    specs: list[RepoSpec] = []
    for rp in repo_paths:
        worktree_name = "code" if len(repo_paths) == 1 else f"code-{rp.name}"
        try:
            user_slug = git_ops.git_user_slug(rp)
        except Exception:
            user_slug = "user"
        branch_prefix_suffix = "-base" if len(repo_paths) == 1 else f"-{rp.name}-base"
        specs.append(
            RepoSpec(
                remote=str(rp),
                local_hint=str(rp),
                worktree=worktree_name,
                branch_prefix=f"{user_slug}/{slug}{branch_prefix_suffix}",
            )
        )
    return specs


def _scaffold_unit(
    *,
    scope: workspace.Scope,
    name: str,
    description: str,
    lifecycle: str,
    repos: list[RepoSpec],
    lc: Lifecycle,
) -> ProjectManifest:
    """Write all the new layout files for a unit (project or deliverable).

    Caller is responsible for the unit-doesn't-exist precheck; this function
    is non-idempotent on existing units.

    Returns the persisted manifest so callers can use it for follow-up steps
    (e.g. worktree creation in `keel new`).
    """
    # Unit root + manifest.
    scope.unit_dir.mkdir(parents=True, exist_ok=True)
    manifest = ProjectManifest(
        project=ProjectMeta(
            name=name,
            description=description,
            created=date.today(),
            lifecycle=lifecycle,
        ),
        repos=repos,
    )
    save_project_manifest(scope.manifest_path, manifest)

    # Tool state under .keel/.
    scope.keel_dir.mkdir(exist_ok=True)
    scope.phase_path.write_text(f"{lc.initial}\n")

    # Lifecycle snapshot — verbatim copy of the resolved TOML.
    src_path = lifecycle_source_path(lifecycle)
    shutil.copyfile(src_path, scope.lifecycle_lock_path)

    # Human-authored content at the unit root.
    scope.scope_md_path.write_text(
        templates.render("scope_md.j2", name=name, description=description)
    )
    scope.design_md_path.write_text(
        templates.render("design_md.j2", name=name, description=description)
    )
    scope.decisions_dir.mkdir(exist_ok=True)

    # README.
    scope.readme_path.write_text(
        templates.render(
            "readme_md.j2",
            project=manifest.project,
            lifecycle=lc,
            phase=lc.initial,
            has_milestones=False,
            repos=manifest.repos,
        )
    )

    return manifest
