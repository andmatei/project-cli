"""`keel deliverable add <name>`."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import typer

from keel import templates, workspace
from keel.manifest import (
    DeliverableManifest, DeliverableMeta,
    save_deliverable_manifest,
)
from keel.output import Output
from keel.prompts import require_or_fail
from keel.util import slugify


def cmd_add(
    name: str = typer.Argument(..., help="Deliverable name (will be slugified)."),
    description: str | None = typer.Option(None, "-d", "--description"),
    project: str | None = typer.Option(None, "--project", "-p", help="Parent project (auto-detected from CWD)."),
    repo: str | None = typer.Option(None, "-r", "--repo", help="Source repo for the deliverable's worktree."),
    shared: bool = typer.Option(False, "--shared", help="Share parent's worktree (no own [[repos]])."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Create a new deliverable inside a project."""
    out = Output(json_mode=json_mode)

    from keel.workspace import resolve_cli_scope
    scope = resolve_cli_scope(project, None, allow_deliverable=False)
    project = scope.project

    slug = slugify(name)
    if not slug:
        out.error("invalid deliverable name", code="invalid_name")
        raise typer.Exit(code=2)

    deliv = workspace.deliverable_dir(project, slug)
    if deliv.exists():
        out.error(f"deliverable already exists: {deliv}", code="exists")
        raise typer.Exit(code=1)

    description = require_or_fail(description, arg_name="--description", label="Description")

    from keel import git_ops
    from keel.manifest import RepoSpec

    # Validate --repo if provided
    repo_path = None
    if repo and shared:
        out.error("--repo and --shared are mutually exclusive", code="conflicting_flags")
        raise typer.Exit(code=2)
    if repo:
        repo_path = Path(repo).expanduser().resolve()
        if not git_ops.is_git_repo(repo_path):
            out.error(f"not a git repo: {repo_path}", code="not_a_repo")
            raise typer.Exit(code=1)

    if dry_run:
        from keel.dryrun import OpLog
        log = OpLog()
        log.create_file(deliv / "design" / "deliverable.toml", size=0)
        log.create_file(deliv / "design" / "CLAUDE.md", size=0)
        log.create_file(deliv / "design" / "design.md", size=0)
        log.create_file(deliv / "design" / ".phase", size=0)
        today = date.today().isoformat()
        log.create_file(deliv / "design" / "decisions" / f"{today}-deliverable-created.md", size=0)
        out.info(log.format_summary())
        return

    # Create directories
    (deliv / "design" / "decisions").mkdir(parents=True)

    # Build manifest
    repo_specs: list[RepoSpec] = []
    if repo_path is not None:
        try:
            user_slug = git_ops.git_user_slug(repo_path)
        except Exception:
            user_slug = "user"
        repo_specs.append(RepoSpec(
            remote=str(repo_path),
            local_hint=str(repo_path),
            worktree="code",
            branch_prefix=f"{user_slug}/{project}-{slug}",
        ))
    manifest = DeliverableManifest(
        deliverable=DeliverableMeta(
            name=slug,
            parent_project=project,
            description=description,
            created=date.today(),
            shared_worktree=shared,
        ),
        repos=repo_specs,
    )
    save_deliverable_manifest(deliv / "design" / "deliverable.toml", manifest)

    # Discover existing siblings for the new deliverable's CLAUDE.md
    existing_siblings: list[dict[str, str]] = []
    siblings_dir_for_render = workspace.project_dir(project) / "deliverables"
    if siblings_dir_for_render.is_dir():
        for sibling in sorted(siblings_dir_for_render.iterdir()):
            if not sibling.is_dir():
                continue
            sib_manifest = sibling / "design" / "deliverable.toml"
            if not sib_manifest.is_file():
                continue
            from keel.manifest import load_deliverable_manifest
            sm = load_deliverable_manifest(sib_manifest)
            existing_siblings.append({"name": sm.deliverable.name, "description": sm.deliverable.description})

    # Templates
    (deliv / "design" / "CLAUDE.md").write_text(
        templates.render(
            "claude_md.j2",
            name=slug, description=description,
            repos=[], deliverables=[], siblings=existing_siblings,
        )
    )
    (deliv / "design" / "design.md").write_text(
        templates.render("design_md.j2", name=slug, description=description)
    )

    # Phase
    (deliv / "design" / ".phase").write_text("scoping\n")

    # Initial decision
    today = date.today().isoformat()
    (deliv / "design" / "decisions" / f"{today}-deliverable-created.md").write_text(
        templates.render("decision_entry.j2", date=today, title=f"Create deliverable {slug}")
    )

    out.info(f"Created deliverable: {deliv}")

    # Create worktree if --repo
    created_worktree = None
    if repo_path is not None:
        wt_dest = deliv / "code"
        try:
            git_ops.create_worktree(repo_path, wt_dest, branch=repo_specs[0].branch_prefix)
            created_worktree = str(wt_dest)
        except git_ops.GitError as e:
            out.error(f"worktree creation failed: {e}", code="git_failed")
            out.info(f"Design files are at {deliv / 'design'}; clean up manually if needed.")
            raise typer.Exit(code=1)

    # AST-edit the parent's CLAUDE.md to list this deliverable
    from keel.markdown_edit import insert_under_heading
    parent_claude_path = workspace.project_dir(project) / "design" / "CLAUDE.md"
    if parent_claude_path.is_file():
        line = f"- **{slug}**: ../deliverables/{slug}/design/ -- {description}\n"
        new_text = insert_under_heading(parent_claude_path.read_text(), "Deliverables", line)
        parent_claude_path.write_text(new_text)

    # AST-edit the parent's design.md
    parent_design_path = workspace.project_dir(project) / "design" / "design.md"
    if parent_design_path.is_file():
        line = f"- **{slug}**: {description}. See [design](../deliverables/{slug}/design/design.md).\n"
        new_text = insert_under_heading(parent_design_path.read_text(), "Deliverables", line)
        parent_design_path.write_text(new_text)

    # AST-edit existing siblings' CLAUDE.md to add this new deliverable
    siblings_dir = workspace.project_dir(project) / "deliverables"
    sibling_modifications = []
    if siblings_dir.is_dir():
        for sibling in sorted(siblings_dir.iterdir()):
            if sibling.name == slug or not sibling.is_dir():
                continue
            sibling_claude = sibling / "design" / "CLAUDE.md"
            if sibling_claude.is_file():
                line = f"- {slug}: ../{slug}/design/ -- {description}\n"
                new_text = insert_under_heading(sibling_claude.read_text(), "Sibling deliverables", line)
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
