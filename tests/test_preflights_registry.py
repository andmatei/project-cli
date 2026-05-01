"""Tests for the phase preflight registry."""

from unittest.mock import MagicMock, patch

from keel.preflights import PreflightResult, iter_preflights
from keel.preflights.builtin import builtin_preflights


def test_iter_preflights_returns_builtins() -> None:
    with patch("keel.preflights.registry.entry_points", return_value=[]):
        items = list(iter_preflights())
    assert len(items) == len(builtin_preflights())


def test_iter_preflights_includes_plugins() -> None:
    class FakePreflight:
        name = "fake"

        def check(self, scope, from_phase, to_phase):
            return PreflightResult()

    fake_ep = MagicMock()
    fake_ep.load.return_value = lambda: [FakePreflight()]
    with patch("keel.preflights.registry.entry_points", return_value=[fake_ep]):
        items = list(iter_preflights())
    names = [p.name for p in items]
    assert "fake" in names


def test_iter_preflights_skips_plugin_load_failures() -> None:
    fake_ep = MagicMock()
    fake_ep.load.side_effect = ImportError("nope")
    with patch("keel.preflights.registry.entry_points", return_value=[fake_ep]):
        items = list(iter_preflights())
    # Should still yield built-ins despite the bad plugin
    assert len(items) == len(builtin_preflights())


def test_iter_preflights_skips_plugin_returning_bad_data() -> None:
    fake_ep = MagicMock()
    fake_ep.load.return_value = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    with patch("keel.preflights.registry.entry_points", return_value=[fake_ep]):
        items = list(iter_preflights())
    assert len(items) == len(builtin_preflights())
