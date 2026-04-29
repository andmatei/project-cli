"""Tests for `keel validate`."""
import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_validate_clean_project(projects, make_project) -> None:
    make_project("foo")
    result = runner.invoke(app, ["validate", "foo"])
    assert result.exit_code == 0


def test_validate_missing_design_md_warns(projects, make_project) -> None:
    proj = make_project("foo")
    (proj / "design" / "design.md").unlink()
    result = runner.invoke(app, ["validate", "foo", "--json"])
    payload = json.loads(result.stdout)
    summary = payload["summary"]
    assert summary["fail"] >= 1 or summary["warn"] >= 1


def test_validate_missing_phase_warns(projects, make_project) -> None:
    proj = make_project("foo")
    (proj / "design" / ".phase").unlink()
    result = runner.invoke(app, ["validate", "foo", "--json"])
    payload = json.loads(result.stdout)
    assert payload["summary"]["fail"] >= 1 or payload["summary"]["warn"] >= 1


def test_validate_orphan_deliverable_dir_warns(projects, make_project, make_deliverable) -> None:
    """A deliverable on disk but not mentioned in parent CLAUDE.md should warn."""
    make_deliverable(project_name="foo", name="bar", description="d")
    # Deliberately strip the parent's mention of this deliverable
    parent_claude = projects / "foo" / "design" / "CLAUDE.md"
    text = parent_claude.read_text()
    parent_claude.write_text(text.replace("- **bar**:", "- **REMOVED**:"))
    result = runner.invoke(app, ["validate", "foo", "--json"])
    payload = json.loads(result.stdout)
    findings = payload["findings"]
    msgs = [f["message"] for f in findings]
    assert any("bar" in m or "missing" in m.lower() for m in msgs)
