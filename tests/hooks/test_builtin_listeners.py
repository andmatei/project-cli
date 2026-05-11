"""Tests for the built-in event listeners (formerly preflights)."""

from __future__ import annotations

import pytest


def test_scope_md_edited_warns_if_scaffold(make_project, projects, monkeypatch) -> None:
    """When leaving 'scoping', warn if scope.md is still the template scaffold."""
    from keel import templates
    from keel.hooks import HookEvent
    from keel.hooks.builtin_listeners import _check_scope_md_edited
    from keel.output import Output

    proj = make_project("foo")
    # scope.md is whatever the fixture wrote — likely template scaffold
    monkeypatch.chdir(proj)

    # Recreate scope.md as the scaffold template so the check fires.
    proj_scope_md = proj / "scope.md"
    proj_scope_md.write_text(templates.render("scope_md.j2", name="foo", description=""))

    event = HookEvent(
        name="phase",
        phase="pre",
        project="foo",
        deliverable=None,
        payload={"from": "scoping", "to": "designing"},
        positional_args=("scoping", "designing"),
    )

    out = Output()
    # _check_scope_md_edited uses out.warn — function returns without raising.
    _check_scope_md_edited(event, out=out)


def test_milestone_exists_blocks_implementing_without_milestones(
    make_project, projects, monkeypatch
) -> None:
    """When entering 'implementing' with no milestones, raise HookAborted."""
    from keel.hooks import HookAborted, HookEvent
    from keel.hooks.builtin_listeners import _check_milestone_exists
    from keel.output import Output

    proj = make_project("foo")
    monkeypatch.chdir(proj)

    event = HookEvent(
        name="phase",
        phase="pre",
        project="foo",
        deliverable=None,
        payload={"from": "poc", "to": "implementing"},
        positional_args=("poc", "implementing"),
    )

    with pytest.raises(HookAborted, match="milestones"):
        _check_milestone_exists(event, out=Output())


def test_milestones_complete_blocks_done(make_project, projects, monkeypatch) -> None:
    """Moving to 'done' with unfinished milestones must abort."""
    from typer.testing import CliRunner

    from keel.app import app
    from keel.hooks import HookAborted, HookEvent
    from keel.hooks.builtin_listeners import _check_milestones_complete
    from keel.output import Output

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])

    event = HookEvent(
        name="phase",
        phase="pre",
        project="foo",
        deliverable=None,
        payload={"from": "shipping", "to": "done"},
        positional_args=("shipping", "done"),
    )
    with pytest.raises(HookAborted, match="unfinished milestones"):
        _check_milestones_complete(event, out=Output())


def test_unrelated_transition_does_nothing(make_project, projects, monkeypatch) -> None:
    """A subscriber that doesn't care about (from, to) returns silently."""
    from keel.hooks import HookEvent
    from keel.hooks.builtin_listeners import _check_milestone_exists
    from keel.output import Output

    proj = make_project("foo")
    monkeypatch.chdir(proj)

    event = HookEvent(
        name="phase",
        phase="pre",
        project="foo",
        deliverable=None,
        payload={"from": "scoping", "to": "designing"},  # not (poc, implementing)
        positional_args=("scoping", "designing"),
    )
    # No raise, no warning expected
    _check_milestone_exists(event, out=Output())


def test_register_builtin_listeners_idempotent() -> None:
    """register_builtin_listeners() can be called multiple times safely."""
    from keel.hooks.builtin_listeners import register_builtin_listeners
    from keel.hooks.registry import _clear_registry, iter_in_tree_subscribers

    _clear_registry()
    register_builtin_listeners()
    first_count = len(list(iter_in_tree_subscribers("pre-phase")))
    register_builtin_listeners()
    second_count = len(list(iter_in_tree_subscribers("pre-phase")))
    assert first_count == second_count
