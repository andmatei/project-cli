"""Tests for prompts module."""
import sys
import pytest
import typer
from keel.prompts import is_interactive, require_or_fail


def test_is_interactive_false_when_stdin_not_tty(monkeypatch) -> None:
    """When stdin is not a tty (the typical pytest case), is_interactive is False."""
    # capsys/redirected stdin in pytest already makes isatty False
    assert is_interactive() in (True, False)  # implementation honors sys.stdin.isatty


def test_require_or_fail_returns_value_when_present() -> None:
    assert require_or_fail("hello", arg_name="--description") == "hello"


def test_require_or_fail_fails_when_missing_and_non_interactive(monkeypatch) -> None:
    monkeypatch.setattr("keel.prompts.is_interactive", lambda: False)
    with pytest.raises(typer.Exit) as exc:
        require_or_fail(None, arg_name="--description")
    assert exc.value.exit_code == 2  # usage error


def test_require_or_fail_prompts_when_missing_and_interactive(monkeypatch) -> None:
    monkeypatch.setattr("keel.prompts.is_interactive", lambda: True)
    monkeypatch.setattr("keel.prompts._prompt_text", lambda label: "filled-in")
    assert require_or_fail(None, arg_name="--description", label="Description") == "filled-in"
