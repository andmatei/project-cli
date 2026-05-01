"""Built-in preflight rules for keel's default phase lifecycle."""

from __future__ import annotations

from keel import templates
from keel.preflights.base import PhasePreflight, PreflightResult
from keel.workspace import Scope


def _template_diff(scope: Scope, filename: str, template_name: str) -> bool:
    """True if the file on disk differs from a fresh template render."""
    path = scope.design_dir / filename
    if not path.is_file():
        return (
            True  # missing file is a "difference" — preflight will flag it elsewhere if it matters
        )
    actual = path.read_text()
    rendered = templates.render(
        template_name,
        name=scope.project,
        description="",  # placeholder; only used to detect "still template"
    )
    return actual.strip() != rendered.strip()


class _ScopeEditedPreflight:
    name = "scope-md-edited"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if (from_phase, to_phase) != ("scoping", "designing"):
            return PreflightResult()
        if not _template_diff(scope, "scope.md", "scope_md.j2"):
            return PreflightResult(warnings=["scope.md is still the template scaffold"])
        return PreflightResult()


class _DesignEditedPreflight:
    name = "design-md-edited"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if (from_phase, to_phase) != ("designing", "poc"):
            return PreflightResult()
        warns: list[str] = []
        if not _template_diff(scope, "design.md", "design_md.j2"):
            warns.append("design.md is still the template scaffold")
        decisions = scope.decisions_dir
        if not decisions.is_dir() or not any(decisions.glob("*.md")):
            warns.append("no decision records under design/decisions/")
        return PreflightResult(warnings=warns)


class _MilestoneExistsPreflight:
    name = "milestone-exists"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if (from_phase, to_phase) != ("poc", "implementing"):
            return PreflightResult()
        from keel.manifest import load_milestones_manifest

        m = load_milestones_manifest(scope.milestones_manifest_path)
        if not m.milestones:
            return PreflightResult(
                blockers=["no milestones defined; add one with 'keel milestone add'"]
            )
        return PreflightResult()


class _MilestonesCompletePreflight:
    name = "milestones-complete"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if to_phase not in ("shipping", "done"):
            return PreflightResult()
        from keel.manifest import load_milestones_manifest

        m = load_milestones_manifest(scope.milestones_manifest_path)
        unfinished = [ms.id for ms in m.milestones if ms.status not in ("done", "cancelled")]
        if not unfinished:
            return PreflightResult()
        msg = f"unfinished milestones: {', '.join(unfinished)}"
        if to_phase == "done":
            return PreflightResult(blockers=[msg])
        return PreflightResult(warnings=[msg])


class _WorktreesCleanPreflight:
    name = "worktrees-clean"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if (from_phase, to_phase) != ("shipping", "done"):
            return PreflightResult()
        from keel import git_ops
        from keel.manifest import load_project_manifest

        try:
            pm = load_project_manifest(scope.manifest_path)
        except Exception:
            return PreflightResult()
        unit_dir = scope.unit_dir
        dirty = []
        for repo in pm.repos:
            wt = unit_dir / repo.worktree
            if wt.is_dir() and git_ops.is_worktree_dirty(wt):
                dirty.append(str(wt))
        if dirty:
            return PreflightResult(warnings=[f"dirty worktrees: {', '.join(dirty)}"])
        return PreflightResult()


def builtin_preflights() -> list[PhasePreflight]:
    """Return the default-lifecycle built-in preflights."""
    return [
        _ScopeEditedPreflight(),
        _DesignEditedPreflight(),
        _MilestoneExistsPreflight(),
        _MilestonesCompletePreflight(),
        _WorktreesCleanPreflight(),
    ]
