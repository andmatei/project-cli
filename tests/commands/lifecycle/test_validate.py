"""Tests for `keel lifecycle validate`."""

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_validate_valid_toml(tmp_path) -> None:
    f = tmp_path / "research.toml"
    f.write_text(
        """
name = "research"
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
""".strip()
    )
    result = runner.invoke(app, ["lifecycle", "validate", str(f)])
    assert result.exit_code == 0
    assert "valid" in result.stdout.lower() or "OK" in result.stdout


def test_validate_unknown_initial_state_fails(tmp_path) -> None:
    f = tmp_path / "broken.toml"
    f.write_text(
        """
name = "broken"
initial = "ghost"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
""".strip()
    )
    result = runner.invoke(app, ["lifecycle", "validate", str(f)])
    assert result.exit_code != 0


def test_validate_filename_mismatch_warns(tmp_path) -> None:
    """If the TOML's `name` differs from the filename stem, warn but don't fail."""
    f = tmp_path / "research.toml"
    f.write_text(
        """
name = "different-name"
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
""".strip()
    )
    result = runner.invoke(app, ["lifecycle", "validate", str(f)])
    # Validation passes (the schema is fine), but a warning surfaces.
    combined = (result.stdout + result.stderr).lower()
    assert "warning" in combined or "mismatch" in combined or "filename" in combined


def test_validate_missing_file_fails(tmp_path) -> None:
    result = runner.invoke(app, ["lifecycle", "validate", str(tmp_path / "nope.toml")])
    assert result.exit_code != 0
