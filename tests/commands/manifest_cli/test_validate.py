"""Tests for keel manifest validate command."""

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_manifest_validate_valid_project(projects, make_project) -> None:
    """Test manifest validate with a valid project.toml."""
    proj = make_project("foo")
    result = runner.invoke(app, ["manifest", "validate", str(proj / "design" / "project.toml")])
    assert result.exit_code == 0


def test_manifest_validate_invalid(projects, tmp_path) -> None:
    """Test manifest validate with invalid TOML."""
    bad = tmp_path / "project.toml"
    bad.write_text("[project]\n# missing required fields\n")
    result = runner.invoke(app, ["manifest", "validate", str(bad)])
    assert result.exit_code != 0


def test_manifest_validate_unknown_filename(projects, tmp_path) -> None:
    """Test manifest validate with unknown filename."""
    foo = tmp_path / "random.toml"
    foo.write_text("")
    result = runner.invoke(app, ["manifest", "validate", str(foo)])
    assert result.exit_code != 0
