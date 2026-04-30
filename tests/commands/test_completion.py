"""Tests for `keel completion`."""

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_completion_bash_prints_script() -> None:
    result = runner.invoke(app, ["completion", "bash"])
    assert result.exit_code == 0
    # Typer/Click bash completion contains _KEEL_COMPLETE setup
    assert "complete" in result.stdout.lower()


def test_completion_zsh_prints_script() -> None:
    result = runner.invoke(app, ["completion", "zsh"])
    assert result.exit_code == 0
    # Zsh completion uses #compdef
    assert (
        "#compdef" in result.stdout
        or "compdef" in result.stdout
        or "complete" in result.stdout.lower()
    )


def test_completion_fish_prints_script() -> None:
    result = runner.invoke(app, ["completion", "fish"])
    assert result.exit_code == 0
    assert "complete" in result.stdout.lower()


def test_completion_unsupported_shell() -> None:
    result = runner.invoke(app, ["completion", "csh"])
    assert result.exit_code != 0
