"""Tests for built-in preflight rules."""

from keel import templates
from keel.manifest import (
    Milestone,
    MilestonesManifest,
    save_milestones_manifest,
)
from keel.preflights.builtin import (
    _DesignEditedPreflight,
    _MilestoneExistsPreflight,
    _MilestonesCompletePreflight,
    _ScopeEditedPreflight,
    _WorktreesCleanPreflight,
)
from keel.workspace import Scope


def test_scope_edited_warns_when_template(make_project) -> None:
    """Scope.md still being template should warn on scoping->designing."""
    proj = make_project("foo")
    # Overwrite with template-like content (empty description)
    (proj / "design" / "scope.md").write_text(
        templates.render("scope_md.j2", name="foo", description="")
    )
    scope = Scope(project="foo", deliverable=None)
    r = _ScopeEditedPreflight().check(scope, "scoping", "designing")
    assert len(r.warnings) == 1
    assert "template" in r.warnings[0].lower()


def test_scope_edited_clean_when_modified(make_project) -> None:
    """Modified scope.md should pass on scoping->designing."""
    proj = make_project("foo")
    (proj / "design" / "scope.md").write_text("# foo\n\nReal content here.")
    scope = Scope(project="foo", deliverable=None)
    r = _ScopeEditedPreflight().check(scope, "scoping", "designing")
    assert r.ok


def test_scope_edited_ignores_other_transitions(make_project) -> None:
    """Scope-edited preflight should only care about scoping->designing."""
    make_project("foo")
    scope = Scope(project="foo", deliverable=None)
    r = _ScopeEditedPreflight().check(scope, "designing", "poc")
    assert r.ok
    r = _ScopeEditedPreflight().check(scope, "scoping", "poc")
    assert r.ok


def test_design_edited_warns_when_template(make_project) -> None:
    """Design.md still being template should warn on designing->poc."""
    proj = make_project("foo")
    # Overwrite with template-like content (empty description)
    (proj / "design" / "design.md").write_text(
        templates.render("design_md.j2", name="foo", description="")
    )
    scope = Scope(project="foo", deliverable=None)
    r = _DesignEditedPreflight().check(scope, "designing", "poc")
    # Both design.md template and no decisions should warn
    assert len(r.warnings) >= 1
    assert any("design.md" in w.lower() for w in r.warnings)


def test_design_edited_warns_when_no_decisions(make_project) -> None:
    """Missing decision records should warn on designing->poc."""
    proj = make_project("foo")
    # Remove the decisions directory to simulate no decisions
    (proj / "design" / "decisions").rmdir()
    scope = Scope(project="foo", deliverable=None)
    r = _DesignEditedPreflight().check(scope, "designing", "poc")
    assert len(r.warnings) >= 1
    assert any("decision" in w.lower() for w in r.warnings)


def test_design_edited_clean_when_both_done(make_project) -> None:
    """Modified design.md with decisions should pass on designing->poc."""
    proj = make_project("foo")
    # Modify design.md to be different from template
    (proj / "design" / "design.md").write_text("# Real design\n\nFull custom content here.")
    (proj / "design" / "decisions" / "2026-01-01-test.md").write_text("# Decision\n")
    scope = Scope(project="foo", deliverable=None)
    r = _DesignEditedPreflight().check(scope, "designing", "poc")
    assert r.ok


def test_design_edited_ignores_other_transitions(make_project) -> None:
    """Design-edited preflight should only care about designing->poc."""
    make_project("foo")
    scope = Scope(project="foo", deliverable=None)
    r = _DesignEditedPreflight().check(scope, "scoping", "designing")
    assert r.ok
    r = _DesignEditedPreflight().check(scope, "poc", "implementing")
    assert r.ok


def test_milestone_exists_blocks_when_empty(make_project) -> None:
    """Empty milestones should block poc->implementing."""
    make_project("foo")
    scope = Scope(project="foo", deliverable=None)
    r = _MilestoneExistsPreflight().check(scope, "poc", "implementing")
    assert len(r.blockers) == 1
    assert "milestone" in r.blockers[0].lower()


def test_milestone_exists_passes_when_present(make_project) -> None:
    """Existing milestone should pass poc->implementing."""
    proj = make_project("foo")
    m = MilestonesManifest(milestones=[Milestone(id="m1", title="Test", status="planned")])
    save_milestones_manifest(proj / "design" / "milestones.toml", m)
    scope = Scope(project="foo", deliverable=None)
    r = _MilestoneExistsPreflight().check(scope, "poc", "implementing")
    assert r.ok


def test_milestone_exists_ignores_other_transitions(make_project) -> None:
    """Milestone-exists preflight should only care about poc->implementing."""
    make_project("foo")
    scope = Scope(project="foo", deliverable=None)
    r = _MilestoneExistsPreflight().check(scope, "designing", "poc")
    assert r.ok
    r = _MilestoneExistsPreflight().check(scope, "implementing", "shipping")
    assert r.ok


def test_milestones_complete_warns_on_shipping_with_unfinished(make_project) -> None:
    """Unfinished milestones should warn on implementing->shipping."""
    proj = make_project("foo")
    m = MilestonesManifest(
        milestones=[
            Milestone(id="m1", title="Done", status="done"),
            Milestone(id="m2", title="Unfinished", status="planned"),
        ]
    )
    save_milestones_manifest(proj / "design" / "milestones.toml", m)
    scope = Scope(project="foo", deliverable=None)
    r = _MilestonesCompletePreflight().check(scope, "implementing", "shipping")
    assert len(r.warnings) == 1
    assert "m2" in r.warnings[0]


def test_milestones_complete_blocks_on_done_with_unfinished(make_project) -> None:
    """Unfinished milestones should block shipping->done."""
    proj = make_project("foo")
    m = MilestonesManifest(
        milestones=[
            Milestone(id="m1", title="Done", status="done"),
            Milestone(id="m2", title="Unfinished", status="active"),
        ]
    )
    save_milestones_manifest(proj / "design" / "milestones.toml", m)
    scope = Scope(project="foo", deliverable=None)
    r = _MilestonesCompletePreflight().check(scope, "shipping", "done")
    assert len(r.blockers) == 1
    assert "m2" in r.blockers[0]


def test_milestones_complete_passes_when_all_done(make_project) -> None:
    """All done/cancelled milestones should pass shipping->done."""
    proj = make_project("foo")
    m = MilestonesManifest(
        milestones=[
            Milestone(id="m1", title="Done", status="done"),
            Milestone(id="m2", title="Cancelled", status="cancelled"),
        ]
    )
    save_milestones_manifest(proj / "design" / "milestones.toml", m)
    scope = Scope(project="foo", deliverable=None)
    r = _MilestonesCompletePreflight().check(scope, "shipping", "done")
    assert r.ok


def test_milestones_complete_ignores_other_transitions(make_project) -> None:
    """Milestones-complete should only care about ->shipping and ->done."""
    proj = make_project("foo")
    m = MilestonesManifest(milestones=[Milestone(id="m1", title="Unfinished", status="planned")])
    save_milestones_manifest(proj / "design" / "milestones.toml", m)
    scope = Scope(project="foo", deliverable=None)
    r = _MilestonesCompletePreflight().check(scope, "poc", "implementing")
    assert r.ok


def test_worktrees_clean_ignores_shipping_non_done(make_project) -> None:
    """Worktrees-clean should only care about shipping->done."""
    make_project("foo")
    scope = Scope(project="foo", deliverable=None)
    r = _WorktreesCleanPreflight().check(scope, "implementing", "shipping")
    assert r.ok


def test_worktrees_clean_no_repos_passes(make_project) -> None:
    """No repos in manifest should pass shipping->done."""
    make_project("foo")
    scope = Scope(project="foo", deliverable=None)
    r = _WorktreesCleanPreflight().check(scope, "shipping", "done")
    assert r.ok
