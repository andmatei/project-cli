"""`keel migrate` — convert legacy Bash CLI projects to manifest format."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import typer

from keel import git_ops, workspace
from keel.api import (
    HINT_LIST_PROJECTS,
    HINT_PASS_PROJECT,
    DeliverableManifest,
    DeliverableMeta,
    ErrorCode,
    Output,
    ProjectManifest,
    ProjectMeta,
    RepoSpec,
    save_deliverable_manifest,
    save_project_manifest,
)

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


def _migrate_deliverables(proj_dir: Path, project_name: str, apply: bool, out) -> int:  # noqa: ANN001
    """Migrate each deliverable under proj_dir/deliverables/.

    Returns count of deliverables migrated (or that would be in dry-run).
    """
    deliv_dir = proj_dir / "deliverables"
    if not deliv_dir.is_dir():
        return 0

    count = 0
    for deliv in sorted(deliv_dir.iterdir()):
        if not deliv.is_dir():
            continue
        manifest_path = deliv / "design" / "deliverable.toml"
        if manifest_path.is_file():
            continue  # already migrated, leave alone
        claude_md = deliv / "design" / "CLAUDE.md"
        if not claude_md.is_file():
            continue

        text = claude_md.read_text()
        repos, shared = _parse_code_section(text, deliv.name)
        repos = _enrich_with_worktree_state(deliv, repos)
        desc = _extract_description(text) or "[migrated]"

        manifest = DeliverableManifest(
            deliverable=DeliverableMeta(
                name=deliv.name,
                parent_project=project_name,
                description=desc,
                created=date.today(),
                shared_worktree=shared,
            ),
            repos=repos,
        )

        if apply:
            save_deliverable_manifest(manifest_path, manifest)
            # Initialize .phase if missing
            phase_file = workspace.phase_file(project_name, deliv.name)
            if not phase_file.is_file():
                phase_file.write_text("scoping\n")
            out.info(f"  deliverable {deliv.name}: wrote {manifest_path}")
        else:
            out.info(f"  [dry-run] deliverable {deliv.name}: would write deliverable.toml")
        count += 1
    return count


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
    """Migrate a project (or all projects) from Bash-CLI format to manifest format.

    Default is dry-run; pass --apply to write.
    """
    out = Output.from_context(ctx, json_mode=json_mode)

    if all_projects:
        targets = []
        root = workspace.projects_dir()
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if child.is_dir() and (child / "design" / "CLAUDE.md").is_file():
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
        if not (workspace.project_dir(name) / "design" / "CLAUDE.md").is_file():
            out.fail(f"not a project: {name}\n  {HINT_LIST_PROJECTS}", code=ErrorCode.NOT_FOUND)
        targets = [name]

    results: list[dict] = []
    for target in targets:
        proj_dir = workspace.project_dir(target)
        manifest_path = workspace.manifest_path(target)
        if manifest_path.is_file():
            out.info(f"{target}: already migrated, skipping")
            results.append({"name": target, "status": "skipped"})
            continue

        claude_md = proj_dir / "design" / "CLAUDE.md"
        if not claude_md.is_file():
            out.warn(f"{target}: no CLAUDE.md, skipping")
            results.append({"name": target, "status": "skipped"})
            continue

        text = claude_md.read_text()
        repos, _shared = _parse_code_section(text, target)
        repos = _enrich_with_worktree_state(proj_dir, repos)

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
            save_project_manifest(manifest_path, manifest)
            out.info(f"{target}: wrote {manifest_path}")
            results.append({"name": target, "status": "migrated", "repos": len(repos)})
        else:
            out.info(f"[dry-run] {target}: would write project.toml with {len(repos)} repo(s)")
            results.append({"name": target, "status": "dry-run", "repos": len(repos)})

        # Migrate deliverables under this project
        d_count = _migrate_deliverables(proj_dir, target, apply, out)
        if results and isinstance(results[-1], dict):
            results[-1]["deliverables"] = d_count

    out.result({"results": results}, human_text=f"Processed {len(results)} project(s).")
