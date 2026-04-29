"""Tests for `keel migrate` (legacy Bash CLI projects → manifests)."""
from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def _write_legacy_project(projects, name: str, body: str) -> None:
    """Helper: scaffold a project in the old Bash CLI shape (no manifest)."""
    proj = projects / name
    (proj / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "CLAUDE.md").write_text(body)
    (proj / "design" / "scope.md").write_text(f"# {name}\nScope.\n")
    (proj / "design" / "design.md").write_text(f"# {name}\nDesign.\n")
    (proj / "design" / ".phase").write_text("scoping\n")


def test_migrate_dry_run_default(projects) -> None:
    """Without --apply, migrate must not write anything."""
    _write_legacy_project(projects, "legacy", "# legacy\n\nold project.\n\n## Code\nCode: ../code/\nSource repo: /tmp/some-repo\n\n## Workflow\n")
    result = runner.invoke(app, ["migrate", "legacy"])
    assert result.exit_code == 0
    assert not (projects / "legacy" / "design" / "project.toml").exists()


def test_migrate_unknown_project(projects) -> None:
    result = runner.invoke(app, ["migrate", "ghost"])
    assert result.exit_code == 1


def test_migrate_skips_already_migrated(projects, make_project) -> None:
    """If project.toml already exists, migrate is a no-op (info, exit 0)."""
    make_project("foo")  # already has project.toml
    result = runner.invoke(app, ["migrate", "foo"])
    assert result.exit_code == 0
    assert "already" in result.stderr.lower() or "skipping" in result.stderr.lower()
