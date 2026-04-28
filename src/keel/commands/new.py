"""`project-cli new <name>`."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import re
import typer

from keel import templates, workspace
from keel.manifest import (
    ProjectManifest, ProjectMeta,
    save_project_manifest,
)
from keel.output import Output
from keel.prompts import require_or_fail


_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(name: str) -> str:
    s = name.lower().strip().replace(" ", "-")
    s = _SLUG_RE.sub("", s)
    return s


def cmd_new(
    name: str = typer.Argument(..., help="Project name (will be slugified)."),
    description: str | None = typer.Option(None, "-d", "--description"),
    repos: list[str] | None = typer.Option(None, "-r", "--repo", help="Source repo path (repeatable)."),
    no_worktree: bool = typer.Option(False, "--no-worktree"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Create a new project workspace."""
    from keel import git_ops

    out = Output(json_mode=json_mode)
    slug = _slugify(name)
    if not slug:
        out.error("invalid project name", code="invalid_name")
        raise typer.Exit(code=2)

    proj = workspace.project_dir(slug)
    if proj.exists():
        out.error(f"project already exists: {proj}", code="exists")
        raise typer.Exit(code=1)

    description = require_or_fail(description, arg_name="--description", label="Description")

    # Resolve and validate repos up front
    repo_paths: list[Path] = []
    if repos and not no_worktree:
        for r in repos:
            rp = Path(r).expanduser().resolve()
            if not git_ops.is_git_repo(rp):
                out.error(f"not a git repo: {rp}", code="not_a_repo")
                raise typer.Exit(code=1)
            repo_paths.append(rp)

    if dry_run:
        from keel.dryrun import OpLog
        log = OpLog()
        log.create_file(proj / "design" / "project.toml", size=0)
        log.create_file(proj / "design" / "CLAUDE.md", size=0)
        log.create_file(proj / "design" / "scope.md", size=0)
        log.create_file(proj / "design" / "design.md", size=0)
        log.create_file(proj / "design" / ".phase", size=0)
        today = date.today().isoformat()
        log.create_file(proj / "design" / "decisions" / f"{today}-project-setup.md", size=0)
        for rp in repo_paths:
            wt_name = "code" if len(repo_paths) == 1 else f"code-{rp.name}"
            try:
                user_slug = git_ops.git_user_slug(rp)
            except Exception:
                user_slug = "user"
            suffix = "-base" if len(repo_paths) == 1 else f"-{rp.name}-base"
            log.create_worktree(proj / wt_name, source=rp, branch=f"{user_slug}/{slug}{suffix}")
        out.info(log.format_summary())
        return

    # Make directories
    (proj / "design" / "decisions").mkdir(parents=True)

    # Build manifest with repos (worktree path defaults to "code" when single, "code-<repo>" otherwise)
    from keel.manifest import RepoSpec
    repo_specs: list[RepoSpec] = []
    for rp in repo_paths:
        worktree_name = "code" if len(repo_paths) == 1 else f"code-{rp.name}"
        try:
            user_slug = git_ops.git_user_slug(rp)
        except Exception:
            user_slug = "user"
        branch_prefix_suffix = "-base" if len(repo_paths) == 1 else f"-{rp.name}-base"
        repo_specs.append(RepoSpec(
            remote=str(rp),
            local_hint=str(rp),
            worktree=worktree_name,
            branch_prefix=f"{user_slug}/{slug}{branch_prefix_suffix}",
        ))

    manifest = ProjectManifest(
        project=ProjectMeta(name=slug, description=description, created=date.today()),
        repos=repo_specs,
    )
    save_project_manifest(proj / "design" / "project.toml", manifest)

    # Templates
    repos_for_template = [{"worktree": r.worktree, "remote": r.remote, "local_hint": r.local_hint} for r in repo_specs]
    (proj / "design" / "CLAUDE.md").write_text(
        templates.render("claude_md.j2", name=slug, description=description, repos=repos_for_template, deliverables=[])
    )
    (proj / "design" / "scope.md").write_text(
        templates.render("scope_md.j2", name=slug, description=description)
    )
    (proj / "design" / "design.md").write_text(
        templates.render("design_md.j2", name=slug, description=description)
    )

    # Phase
    (proj / "design" / ".phase").write_text("scoping\n")

    # Initial decision file
    today = date.today().isoformat()
    decision_path = proj / "design" / "decisions" / f"{today}-project-setup.md"
    decision_path.write_text(
        templates.render("decision_entry.j2", date=today, title="Project workspace setup")
    )

    # Worktrees (last — file ops above already done)
    created_worktrees: list[str] = []
    for rp, spec in zip(repo_paths, repo_specs):
        wt_dest = proj / spec.worktree
        try:
            git_ops.create_worktree(rp, wt_dest, branch=spec.branch_prefix)
            created_worktrees.append(str(wt_dest))
        except git_ops.GitError as e:
            out.error(f"worktree creation failed: {e}", code="git_failed")
            out.info(f"Design files are at {proj / 'design'}; clean up with `rm -rf {proj}` or retry.")
            raise typer.Exit(code=1)

    out.info(f"Created project: {proj}")
    out.result(
        {"path": str(proj), "design": str(proj / "design"), "worktrees": created_worktrees},
        human_text=f"Project created: {proj}",
    )
