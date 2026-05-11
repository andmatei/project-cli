"""Tests for keel.hooks types."""

from __future__ import annotations

import pytest


def test_hook_event_construction() -> None:
    from keel.hooks import HookEvent

    event = HookEvent(
        name="new",
        phase="pre",
        project="foo",
        deliverable=None,
        payload={"description": "test"},
        positional_args=("foo",),
    )
    assert event.name == "new"
    assert event.phase == "pre"
    assert event.project == "foo"
    assert event.deliverable is None
    assert event.payload == {"description": "test"}
    assert event.positional_args == ("foo",)


def test_hook_event_is_frozen() -> None:
    """HookEvent must be immutable so subscribers can't mutate shared state."""
    from dataclasses import FrozenInstanceError

    from keel.hooks import HookEvent

    event = HookEvent(
        name="new", phase="pre", project="foo", deliverable=None,
        payload={}, positional_args=(),
    )
    with pytest.raises(FrozenInstanceError):
        event.name = "phase"  # type: ignore[misc]


def test_hook_event_full_name() -> None:
    """full_name returns 'pre-<name>' or 'post-<name>'."""
    from keel.hooks import HookEvent

    pre = HookEvent(name="new", phase="pre", project=None, deliverable=None, payload={}, positional_args=())
    post = HookEvent(name="phase", phase="post", project="foo", deliverable=None, payload={}, positional_args=())
    assert pre.full_name == "pre-new"
    assert post.full_name == "post-phase"


def test_hook_aborted_is_runtime_error() -> None:
    """HookAborted must be catchable as RuntimeError for natural error handling."""
    from keel.hooks import HookAborted

    err = HookAborted("blocked because reasons")
    assert isinstance(err, RuntimeError)
    assert str(err) == "blocked because reasons"
