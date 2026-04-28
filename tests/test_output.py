"""Tests for the output module."""
from __future__ import annotations
import json
import io
from keel.output import Output


def test_info_goes_to_stderr(capsys) -> None:
    o = Output(quiet=False)
    o.info("hello")
    captured = capsys.readouterr()
    assert "hello" in captured.err
    assert captured.out == ""


def test_quiet_suppresses_info(capsys) -> None:
    o = Output(quiet=True)
    o.info("hello")
    assert capsys.readouterr().err == ""


def test_error_always_stderr(capsys) -> None:
    o = Output(quiet=True)
    o.error("oops")
    assert "oops" in capsys.readouterr().err


def test_print_result_human_to_stdout(capsys) -> None:
    o = Output(json_mode=False)
    o.result({"path": "/p"}, human_text="created at /p")
    captured = capsys.readouterr()
    assert "created at /p" in captured.out


def test_print_result_json_to_stdout(capsys) -> None:
    o = Output(json_mode=True)
    o.result({"path": "/p"})
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"path": "/p"}


def test_print_error_json(capsys) -> None:
    o = Output(json_mode=True)
    o.error("oops", code="not_found")
    captured = capsys.readouterr()
    assert json.loads(captured.err) == {"error": "oops", "code": "not_found"}


def test_info_preserves_bracketed_text(capsys) -> None:
    """[bracketed] prefixes (e.g., [dry-run]) must not be consumed as Rich markup."""
    o = Output(quiet=False)
    o.info("[dry-run] Would create /p/a")
    captured = capsys.readouterr()
    assert "[dry-run]" in captured.err
    assert "Would create /p/a" in captured.err


def test_result_json_is_parseable_long_payload(capsys) -> None:
    """Long JSON payloads must not be wrapped (must remain valid JSON)."""
    o = Output(json_mode=True)
    long_path = "/" + "x" * 200  # forces wrapping if Rich is in the loop
    o.result({"path": long_path, "items": [f"item-{i}" for i in range(20)]})
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["path"] == long_path
    assert len(payload["items"]) == 20


def test_warn_goes_to_stderr_with_yellow(capsys) -> None:
    o = Output(quiet=False)
    o.warn("careful now")
    captured = capsys.readouterr()
    assert "careful now" in captured.err
    assert captured.out == ""


def test_warn_suppressed_when_quiet(capsys) -> None:
    o = Output(quiet=True)
    o.warn("careful now")
    assert capsys.readouterr().err == ""


def test_from_context_picks_up_quiet() -> None:
    """Output.from_context honors quiet=True from ctx.obj."""
    class _Ctx:
        obj = {"quiet": True, "verbose": False}
    o = Output.from_context(_Ctx())
    assert o.quiet is True


def test_from_context_picks_up_verbose() -> None:
    class _Ctx:
        obj = {"quiet": False, "verbose": True}
    o = Output.from_context(_Ctx())
    assert o.verbose is True


def test_from_context_with_json_mode_overrides_quiet() -> None:
    """--json forces quiet (existing constructor behavior)."""
    class _Ctx:
        obj = {"quiet": False, "verbose": False}
    o = Output.from_context(_Ctx(), json_mode=True)
    assert o.json_mode is True
    assert o.quiet is True


def test_from_context_handles_no_ctx_obj() -> None:
    """Don't crash if ctx.obj is None (subcommand invoked without root callback)."""
    class _Ctx:
        obj = None
    o = Output.from_context(_Ctx())
    assert o.quiet is False
    assert o.verbose is False
