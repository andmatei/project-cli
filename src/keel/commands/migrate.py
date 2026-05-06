"""`keel migrate` — convert legacy Bash CLI projects to manifest format and
rewrite the on-disk layout to the new (v0.1.0) shape.

Two phases:
1. Bash CLI → manifest detection / conversion (creates a manifest from
   `design/CLAUDE.md`).
2. Legacy `design/` layout → new layout (manifests + README + .keel/ at the
   unit root). Idempotent: re-running on an already-migrated unit is a no-op.
"""

from __future__ import annotations

import contextlib
import re
import shutil
from datetime import date
from pathlib import Path

import typer

from keel import git_ops, templates, workspace
from keel.api import (
    HINT_LIST_PROJECTS,
    HINT_PASS_PROJECT,
    ErrorCode,
    Output,
    ProjectManifest,
    ProjectMeta,
    RepoSpec,
    save_project_manifest,
)
from keel.lifecycles import LifecycleNotFoundError
from keel.lifecycles.loader import lifecycle_source_path, load_lifecycle

_CODE_SECTION_RE = re.compile(r"## Code\n(.*?)(?:\n## |\Z)", re.DOTALL)
_SINGLE_CODE_RE = re.compile(r"^Code:\s+\.\./code/?\s*$", re.MULTILINE)
_MULTI_CODE_RE = re.compile(r"^Code\s+\(([^)]+)\):\s+\.\./code-([^/\s]+)/?\s*$", re.MULTILINE)
_SHARED_CODE_RE = re.compile(r"^Code:\s+shared with parent", re.MULTILINE)
_SOURCE_REPO_RE = re.compile(r"^Source repo:\s+(.+?)\s*$", re.MULTILINE)
_SOURCE_REPOS_RE = re.compile(r"^Source repos:\s+(.+?)\s*$", re.MULTILINE)


def _parse_code_section(claude_md_text: str, project_name: str) -> tuple[list, bool]:
    """Parse a legacy CLAUDE.md '## Code' section.

    Returns (list[RepoSpec], shared_worktree).
    """
    section_match = _CODE_SECTION_RE.search(claude_md_text)
    if not section_match:
        return [], False
    section = section_match.group(1)

    if _SHARED_CODE_RE.search(section):
        return [], True

    repos: list[RepoSpec] = []

    # Multi-repo: collect all "Code (<name>): ../code-<name>/" lines
    multi_matches = list(_MULTI_CODE_RE.finditer(section))
    if multi_matches:
        # Source repos line: space-separated paths
        source_repos_line = _SOURCE_REPOS_RE.search(section)
        source_paths = source_repos_line.group(1).split() if source_repos_line else []
        # Map each entry by basename to the corresponding code-<x> dir
        for m in multi_matches:
            code_name = m.group(1)  # e.g. "mms"
            wt_name = f"code-{m.group(2)}"
            # Find the matching source path by basename
            remote = next((p for p in source_paths if Path(p).name == code_name), None) or ""
            repos.append(
                RepoSpec(
                    remote=remote,
                    local_hint=remote or None,
                    worktree=wt_name,
                    branch_prefix=None,
                )
            )
        return repos, False

    # Single-repo
    if _SINGLE_CODE_RE.search(section):
        source_match = _SOURCE_REPO_RE.search(section)
        if source_match:
            remote = source_match.group(1).strip()
            repos.append(
                RepoSpec(
                    remote=remote,
                    local_hint=remote,
                    worktree="code",
                    branch_prefix=None,
                )
            )
        return repos, False

    # Design-only or unrecognized — return empty
    return [], False


def _enrich_with_worktree_state(unit_dir: Path, repos: list) -> list:
    """For each repo with a worktree on disk, fill branch_prefix from the current branch."""

    enriched: list[RepoSpec] = []
    for r in repos:
        wt = unit_dir / r.worktree
        prefix = r.branch_prefix
        if prefix is None and wt.is_dir() and git_ops.is_git_repo(wt):
            try:
                cur = git_ops.current_branch(wt)
                if cur:
                    prefix = cur
            except git_ops.GitError:
                pass
        enriched.append(
            RepoSpec(
                remote=r.remote,
                local_hint=r.local_hint,
                worktree=r.worktree,
                branch_prefix=prefix,
            )
        )
    return enriched


_TITLE_RE = re.compile(r"^# (.+?)\s*$", re.MULTILINE)


def _extract_description(text: str) -> str | None:
    """Heuristic: the first non-empty line after '# Title' is the description."""
    title_match = _TITLE_RE.search(text)
    if not title_match:
        return None
    after = text[title_match.end() :].lstrip("\n")
    for line in after.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def _is_legacy_unit(unit_dir: Path) -> bool:
    """Return True if `unit_dir` looks like a legacy unit needing migration.

    A legacy unit either:
    - has a `design/CLAUDE.md` (pre-keel-manifest Bash CLI shape), or
    - has a `design/project.toml` or `design/deliverable.toml` (manifest exists
      but at the legacy path).
    """
    design = unit_dir / "design"
    if not design.is_dir():
        return False
    return (
        (design / "CLAUDE.md").is_file()
        or (design / "project.toml").is_file()
        or (design / "deliverable.toml").is_file()
    )


def _migrate_deliverable_bash_cli(deliv: Path, project_name: str, apply: bool, out) -> bool:  # noqa: ANN001
    """Bash-CLI → manifest conversion for a single deliverable.

    Returns True if a manifest was written (or would be in dry-run), False if
    the deliverable already has a manifest or has no CLAUDE.md to migrate.

    Writes the new manifest at `<deliv>/design/project.toml` (the legacy layout
    location, matching `design/CLAUDE.md`). The follow-up legacy-layout
    migration step moves it up to `<deliv>/project.toml`.
    """
    if (
        (deliv / "design" / "project.toml").is_file()
        or (deliv / "design" / "deliverable.toml").is_file()
        or (deliv / "project.toml").is_file()
    ):
        return False  # already has a manifest somewhere
    claude_md = deliv / "design" / "CLAUDE.md"
    if not claude_md.is_file():
        return False

    text = claude_md.read_text()
    repos, shared = _parse_code_section(text, deliv.name)
    repos = _enrich_with_worktree_state(deliv, repos)
    desc = _extract_description(text) or "[migrated]"

    manifest = ProjectManifest(
        project=ProjectMeta(
            name=deliv.name,
            description=desc,
            created=date.today(),
            shared_worktree=shared,
        ),
        repos=repos,
    )

    if apply:
        manifest_path = deliv / "design" / "project.toml"
        save_project_manifest(manifest_path, manifest)
        # Initialize legacy-style .phase if missing — _migrate_legacy_layout
        # will move it into .keel/ shortly after.
        legacy_phase = deliv / "design" / ".phase"
        if not legacy_phase.is_file():
            legacy_phase.write_text("scoping\n")
        out.info(f"  deliverable {deliv.name}: wrote {manifest_path}")
    else:
        out.info(f"  [dry-run] deliverable {deliv.name}: would write project.toml")
    return True


def _migrate_legacy_layout(unit_dir: Path, lifecycle_name: str = "default") -> bool:
    """Rewrite a unit's layout from the legacy `design/` layout to the new layout.

    Returns True if any change was made; False if already migrated.
    """
    design_dir = unit_dir / "design"
    if not design_dir.is_dir():
        return False  # Already migrated or never had legacy layout

    # 1. Move manifests
    if (design_dir / "project.toml").is_file():
        (design_dir / "project.toml").rename(unit_dir / "project.toml")
    elif (design_dir / "deliverable.toml").is_file():
        # Convert deliverable → project
        from keel.manifest.io import load_deliverable_manifest

        pm = load_deliverable_manifest(design_dir / "deliverable.toml")
        save_project_manifest(unit_dir / "project.toml", pm)
        (design_dir / "deliverable.toml").unlink()

    if (design_dir / "milestones.toml").is_file():
        (design_dir / "milestones.toml").rename(unit_dir / "milestones.toml")

    # 2. .keel/ directory
    keel_dir = unit_dir / ".keel"
    keel_dir.mkdir(exist_ok=True)
    if (design_dir / ".phase").is_file():
        (design_dir / ".phase").rename(keel_dir / "phase")

    # 3. Lifecycle snapshot
    lock_path = keel_dir / "lifecycle.lock.toml"
    if not lock_path.is_file():
        try:
            src = lifecycle_source_path(lifecycle_name)
            shutil.copyfile(src, lock_path)
        except LifecycleNotFoundError:
            pass  # leave a placeholder (no snapshot)

    # 4. Move human content up
    for item in ("scope.md", "design.md", "decisions", "plans", "specs"):
        src = design_dir / item
        if src.exists():
            src.rename(unit_dir / item)

    # 5. Generate README if missing
    readme = unit_dir / "README.md"
    if not readme.is_file() and (unit_dir / "project.toml").is_file():
        from keel.manifest import load_project_manifest

        pm = load_project_manifest(unit_dir / "project.toml")
        try:
            lc = load_lifecycle(pm.project.lifecycle)
            phase_text = (
                (keel_dir / "phase").read_text().strip() if (keel_dir / "phase").is_file() else ""
            )
            phase = phase_text or lc.initial
        except Exception:
            lc = None
            phase = "scoping"
        readme.write_text(
            templates.render(
                "readme_md.j2",
                project=pm.project,
                lifecycle=lc or type("L", (), {"name": pm.project.lifecycle}),
                phase=phase,
                has_milestones=(unit_dir / "milestones.toml").is_file(),
                repos=pm.repos,
            )
        )

    # 6. Drop the now-empty design/ directory. If not empty (migrator might
    # have missed something), leave for user inspection.
    with contextlib.suppress(OSError):
        design_dir.rmdir()

    # 7. Recurse into deliverables
    deliverables = unit_dir / "deliverables"
    if deliverables.is_dir():
        for deliv in deliverables.iterdir():
            if deliv.is_dir():
                _migrate_legacy_layout(deliv, lifecycle_name)

    return True


def cmd_migrate(
    ctx: typer.Context,
    name: str | None = typer.Argument(
        None, help="Project name to migrate. Auto-detected from CWD if omitted."
    ),
    all_projects: bool = typer.Option(
        False, "--all", help="Migrate every legacy project under $PROJECTS_DIR."
    ),
    apply: bool = typer.Option(
        False, "--apply", help="Actually write the manifests (default is dry-run preview)."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Migrate a project (or all projects) from Bash-CLI / legacy layout to the
    current manifest + new-layout shape.

    Default is dry-run; pass --apply to write.
    """
    out = Output.from_context(ctx, json_mode=json_mode)

    if all_projects:
        targets: list[str] = []
        root = workspace.projects_dir()
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if not child.is_dir():
                    continue
                # New-layout already-migrated unit: skip silently.
                if (child / "project.toml").is_file():
                    continue
                if _is_legacy_unit(child):
                    targets.append(child.name)
    else:
        if name is None:
            scope = workspace.detect_scope()
            name = scope.project
        if name is None:
            out.fail(
                f"no project specified and none detected from CWD\n  {HINT_PASS_PROJECT}",
                code=ErrorCode.NO_PROJECT,
            )
        proj_dir = workspace.project_dir(name)
        # Already-migrated (new layout): treat as a no-op skip.
        if (proj_dir / "project.toml").is_file():
            out.info(f"{name}: already migrated, skipping")
            out.result(
                {"results": [{"name": name, "status": "skipped"}]},
                human_text="Processed 1 project(s).",
            )
            return
        if not _is_legacy_unit(proj_dir):
            out.fail(f"not a project: {name}\n  {HINT_LIST_PROJECTS}", code=ErrorCode.NOT_FOUND)
        targets = [name]

    results: list[dict] = []
    for target in targets:
        proj_dir = workspace.project_dir(target)

        # Phase 1: Bash CLI → manifest, but only if no manifest yet exists.
        legacy_manifest = proj_dir / "design" / "project.toml"
        new_manifest = proj_dir / "project.toml"
        claude_md = proj_dir / "design" / "CLAUDE.md"

        if new_manifest.is_file():
            out.info(f"{target}: already migrated, skipping")
            results.append({"name": target, "status": "skipped"})
            continue

        repos_count = 0
        if not legacy_manifest.is_file():
            # No manifest yet — try to derive from CLAUDE.md.
            if not claude_md.is_file():
                out.warn(f"{target}: no CLAUDE.md, skipping")
                results.append({"name": target, "status": "skipped"})
                continue

            text = claude_md.read_text()
            repos, _shared = _parse_code_section(text, target)
            repos = _enrich_with_worktree_state(proj_dir, repos)
            repos_count = len(repos)

            desc = _extract_description(text) or "[migrated; description not extracted]"

            manifest = ProjectManifest(
                project=ProjectMeta(
                    name=target,
                    description=desc,
                    created=date.today(),
                ),
                repos=repos,
            )

            if apply:
                save_project_manifest(legacy_manifest, manifest)
                out.info(f"{target}: wrote {legacy_manifest}")
            else:
                out.info(f"[dry-run] {target}: would write project.toml with {len(repos)} repo(s)")

        # Phase 1b: Bash-CLI conversion for any deliverables that need it.
        d_count = 0
        deliv_root = proj_dir / "deliverables"
        if deliv_root.is_dir():
            for deliv in sorted(deliv_root.iterdir()):
                if not deliv.is_dir():
                    continue
                if _migrate_deliverable_bash_cli(deliv, target, apply, out):
                    d_count += 1

        # Phase 2: Legacy layout → new layout (only when --apply; dry-run is a
        # preview-only mode).
        if apply:
            _migrate_legacy_layout(proj_dir)

        results.append(
            {
                "name": target,
                "status": "migrated" if apply else "dry-run",
                "repos": repos_count,
                "deliverables": d_count,
            }
        )

    out.result({"results": results}, human_text=f"Processed {len(results)} project(s).")
