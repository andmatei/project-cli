"""`keel deliverable add <name>`."""

from __future__ import annotations

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
    load_project_manifest,
    require_or_fail,
    resolve_cli_scope,
    save_project_manifest,
    slugify,
)
from keel.markdown_edit import insert_under_heading


def cmd_add(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Deliverable name (will be slugified)."),
    description: str | None = typer.Option(
        None, "-d", "--description", help="Brief deliverable description; required."
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Parent project. Auto-detected from CWD if omitted."
    ),
    repo: str | None = typer.Option(
        None,
        "-r",
        "--repo",
        help="Source git repo for the deliverable's own worktree. Mutually exclusive with --shared.",
    ),
    shared: bool = typer.Option(
        False, "--shared", help="Use the parent project's worktree (no own [[repos]])."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    yes: bool = typer.Option(
        False, "-y", "--yes", help="Skip interactive prompts (description, etc.)."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Create a new deliverable inside a project."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, None, allow_deliverable=False, out=out)
    project = scope.project

    slug = slugify(name)
    if not slug:
        out.fail("invalid deliverable name", code=ErrorCode.INVALID_NAME, exit_code=2)

    deliv_scope = workspace.Scope(project=project, deliverable=slug)
    deliv = deliv_scope.unit_dir
    if deliv.exists():
        out.fail(f"deliverable already exists: {deliv}", code=ErrorCode.EXISTS)

    description = require_or_fail(description, arg_name="--description", label="Description")

    # Validate --repo if provided
    repo_path = None
    if repo and shared:
        out.fail(
            "--repo and --shared are mutually exclusive",
            code=ErrorCode.CONFLICTING_FLAGS,
            exit_code=2,
        )
    if repo:
        repo_path = Path(repo).expanduser().resolve()
        if not git_ops.is_git_repo(repo_path):
            out.fail(f"not a git repo: {repo_path}", code=ErrorCode.NOT_A_REPO)

    if dry_run:
        log = OpLog()
        log.create_file(deliv_scope.manifest_path, size=0)
        log.create_file(deliv_scope.unit_dir / "CLAUDE.md", size=0)
        log.create_file(deliv_scope.design_md_path, size=0)
        log.create_file(deliv_scope.phase_path, size=0)
        today = date.today().isoformat()
        log.create_file(deliv_scope.decisions_dir / f"{today}-deliverable-created.md", size=0)
        out.info(log.format_summary())
        return

    # Create directories
    deliv_scope.decisions_dir.mkdir(parents=True)

    # Build manifest
    repo_specs: list[RepoSpec] = []
    if repo_path is not None:
        try:
            user_slug = git_ops.git_user_slug(repo_path)
        except Exception:
            user_slug = "user"
        repo_specs.append(
            RepoSpec(
                remote=str(repo_path),
                local_hint=str(repo_path),
                worktree="code",
                branch_prefix=f"{user_slug}/{project}-{slug}",
            )
        )
    manifest = ProjectManifest(
        project=ProjectMeta(
            name=slug,
            description=description,
            created=date.today(),
            shared_worktree=shared,
        ),
        repos=repo_specs,
    )
    save_project_manifest(deliv_scope.manifest_path, manifest)

    # Discover existing siblings for the new deliverable's CLAUDE.md
    # TODO(plan8-task9.2): claude_md.j2 / sibling CLAUDE.md handling is dead post-redesign.
    existing_siblings: list[dict[str, str]] = []
    siblings_dir_for_render = workspace.project_dir(project) / "deliverables"
    if siblings_dir_for_render.is_dir():
        for sibling in sorted(siblings_dir_for_render.iterdir()):
            if not sibling.is_dir():
                continue
            sib_manifest = sibling / "project.toml"
            if not sib_manifest.is_file():
                continue
            sm = load_project_manifest(sib_manifest)
            existing_siblings.append(
                {"name": sm.project.name, "description": sm.project.description}
            )

    # Templates
    # TODO(plan8-task9.2): CLAUDE.md is dead post-redesign; leaving generation in place for now.
    (deliv_scope.unit_dir / "CLAUDE.md").write_text(
        templates.render(
            "claude_md.j2",
            name=slug,
            description=description,
            repos=[],
            deliverables=[],
            siblings=existing_siblings,
        )
    )
    deliv_scope.design_md_path.write_text(
        templates.render("design_md.j2", name=slug, description=description)
    )

    # Phase
    deliv_scope.keel_dir.mkdir(parents=True, exist_ok=True)
    deliv_scope.phase_path.write_text("scoping\n")

    # Initial decision
    today = date.today().isoformat()
    (deliv_scope.decisions_dir / f"{today}-deliverable-created.md").write_text(
        templates.render("decision_entry.j2", date=today, title=f"Create deliverable {slug}")
    )

    # Create worktree if --repo
    created_worktree = None
    if repo_path is not None:
        wt_dest = deliv / "code"
        try:
            git_ops.create_worktree(repo_path, wt_dest, branch=repo_specs[0].branch_prefix)
            created_worktree = str(wt_dest)
        except git_ops.GitError as e:
            out.info(f"Design files are at {deliv}; clean up manually if needed.")
            out.fail(f"worktree creation failed: {e}", code=ErrorCode.GIT_FAILED)

    # AST-edit the parent's CLAUDE.md to list this deliverable
    # TODO(plan8-task9.2): CLAUDE.md links are dead post-redesign.
    parent_scope_for_edits = workspace.Scope(project=project, deliverable=None)
    parent_claude_path = parent_scope_for_edits.unit_dir / "CLAUDE.md"
    if parent_claude_path.is_file():
        line = f"- **{slug}**: ../deliverables/{slug}/ -- {description}\n"
        new_text = insert_under_heading(parent_claude_path.read_text(), "Deliverables", line)
        parent_claude_path.write_text(new_text)

    # AST-edit the parent's design.md
    parent_design_path = parent_scope_for_edits.design_md_path
    if parent_design_path.is_file():
        line = f"- **{slug}**: {description}. See [design](../deliverables/{slug}/design.md).\n"
        new_text = insert_under_heading(parent_design_path.read_text(), "Deliverables", line)
        parent_design_path.write_text(new_text)

    # AST-edit existing siblings' CLAUDE.md to add this new deliverable
    # TODO(plan8-task9.2): sibling CLAUDE.md is dead post-redesign.
    siblings_dir = workspace.project_dir(project) / "deliverables"
    sibling_modifications = []
    if siblings_dir.is_dir():
        for sibling in sorted(siblings_dir.iterdir()):
            if sibling.name == slug or not sibling.is_dir():
                continue
            sibling_claude = sibling / "CLAUDE.md"
            if sibling_claude.is_file():
                line = f"- {slug}: ../{slug}/ -- {description}\n"
                new_text = insert_under_heading(
                    sibling_claude.read_text(), "Sibling deliverables", line
                )
                sibling_claude.write_text(new_text)
                sibling_modifications.append(str(sibling_claude))

    modified_files = []
    if parent_claude_path.is_file():
        modified_files.append(str(parent_claude_path))
    if parent_design_path.is_file():
        modified_files.append(str(parent_design_path))
    modified_files.extend(sibling_modifications)
    out.result(
        {
            "deliverable_path": str(deliv),
            "modified_files": modified_files,
            "worktree": created_worktree,
        },
        human_text=f"Deliverable created: {deliv}",
    )
