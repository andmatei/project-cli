"""Tests for the in-tree subscriber registry."""

from __future__ import annotations


def test_subscribes_to_registers_function() -> None:
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry, iter_in_tree_subscribers

    _clear_registry()

    @subscribes_to("pre-new")
    def my_listener(event: HookEvent, *, out) -> None:
        pass

    subs = list(iter_in_tree_subscribers("pre-new"))
    assert len(subs) == 1
    assert subs[0] is my_listener


def test_subscribes_to_preserves_registration_order() -> None:
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry, iter_in_tree_subscribers

    _clear_registry()

    @subscribes_to("post-phase")
    def first(event: HookEvent, *, out) -> None:
        pass

    @subscribes_to("post-phase")
    def second(event: HookEvent, *, out) -> None:
        pass

    subs = list(iter_in_tree_subscribers("post-phase"))
    assert subs == [first, second]


def test_iter_subscribers_empty_for_unknown_event() -> None:
    from keel.hooks.registry import _clear_registry, iter_in_tree_subscribers

    _clear_registry()
    assert list(iter_in_tree_subscribers("pre-unknown")) == []


def test_subscribes_to_rejects_invalid_event_name() -> None:
    """Names must start with 'pre-' or 'post-'."""
    import pytest

    from keel.hooks import subscribes_to

    with pytest.raises(ValueError, match="must start with 'pre-' or 'post-'"):

        @subscribes_to("new")  # missing prefix
        def bad(event, *, out) -> None:
            pass
