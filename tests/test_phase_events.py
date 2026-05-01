"""Tests for keel.phase_transitions event hooks."""

from unittest.mock import MagicMock, patch

from keel.phase_events import (
    fire_phase_transition,
    iter_phase_transition_hooks,
)


def test_iter_hooks_empty_by_default() -> None:
    with patch("keel.phase_events.entry_points", return_value=[]):
        assert iter_phase_transition_hooks() == []


def test_fire_calls_each_hook() -> None:
    calls = []

    def hook_a(scope, from_, to_):
        calls.append(("a", from_, to_))

    def hook_b(scope, from_, to_):
        calls.append(("b", from_, to_))

    out_mock = MagicMock()
    with patch("keel.phase_events.iter_phase_transition_hooks", return_value=[hook_a, hook_b]):
        fire_phase_transition(scope=None, from_phase="x", to_phase="y", out=out_mock)
    assert calls == [("a", "x", "y"), ("b", "x", "y")]


def test_fire_swallows_hook_errors() -> None:
    def bad_hook(scope, from_, to_):
        raise RuntimeError("boom")

    out_mock = MagicMock()
    with patch("keel.phase_events.iter_phase_transition_hooks", return_value=[bad_hook]):
        fire_phase_transition(scope=None, from_phase="x", to_phase="y", out=out_mock)
    out_mock.warn.assert_called_once()


def test_iter_hooks_loads_from_entry_points() -> None:
    def hook(scope, from_, to_):
        pass

    fake_ep = MagicMock()
    fake_ep.load.return_value = hook
    with patch("keel.phase_events.entry_points", return_value=[fake_ep]):
        hooks = iter_phase_transition_hooks()
    assert hook in hooks


def test_iter_hooks_skips_load_failures() -> None:
    fake_ep = MagicMock()
    fake_ep.load.side_effect = ImportError("nope")
    with patch("keel.phase_events.entry_points", return_value=[fake_ep]):
        assert iter_phase_transition_hooks() == []
