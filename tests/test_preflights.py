"""Tests for the preflight framework."""

from keel.preflights import PhasePreflight, PreflightResult


def test_preflight_result_ok_when_empty() -> None:
    r = PreflightResult()
    assert r.ok is True


def test_preflight_result_not_ok_with_warning() -> None:
    r = PreflightResult(warnings=["x"])
    assert r.ok is False


def test_preflight_result_not_ok_with_blocker() -> None:
    r = PreflightResult(blockers=["x"])
    assert r.ok is False


def test_preflight_protocol_is_runtime_checkable() -> None:
    class FakePreflight:
        name = "fake"

        def check(self, scope, from_phase, to_phase):
            return PreflightResult()

    assert isinstance(FakePreflight(), PhasePreflight)
