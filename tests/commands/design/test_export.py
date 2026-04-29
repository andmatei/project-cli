"""Tests for `keel design export`."""
from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_export_deliverable(projects, make_deliverable) -> None:
    """Deliverable-level export produces a single doc with the deliverable's design + decisions."""
    deliv = make_deliverable(project_name="foo", name="bar", description="the bar")
    # Create a decision in the deliverable
    decision_dir = deliv / "design" / "decisions"
    decision_dir.mkdir(parents=True, exist_ok=True)
    (decision_dir / "2026-04-29-pick-x.md").write_text(
        "---\ndate: 2026-04-29\ntitle: Pick X\nstatus: proposed\n---\n# Pick X\n## Question\nQ?\n## Conclusion\nC.\n"
    )
    result = runner.invoke(app, ["design", "export", "--project", "foo", "-D", "bar"])
    assert result.exit_code == 0
    assert "# bar" in result.stdout or "bar" in result.stdout
    assert "Pick X" in result.stdout


def test_export_deliverable_excludes_superseded(projects, make_deliverable) -> None:
    deliv = make_deliverable(project_name="foo", name="bar", description="d")
    decision_dir = deliv / "design" / "decisions"
    decision_dir.mkdir(parents=True, exist_ok=True)
    (decision_dir / "2026-04-29-old.md").write_text(
        "---\ndate: 2026-04-29\ntitle: Old\nstatus: superseded\n---\n# Old\n## Question\nQ?\n## Conclusion\nC.\n"
    )
    (decision_dir / "2026-04-29-new.md").write_text(
        "---\ndate: 2026-04-29\ntitle: New\nstatus: proposed\n---\n# New\n## Question\nQ?\n## Conclusion\nC.\n"
    )
    result = runner.invoke(app, ["design", "export", "--project", "foo", "-D", "bar"])
    assert "New" in result.stdout
    assert "Old" not in result.stdout


def test_export_writes_to_output_file(projects, make_deliverable, tmp_path) -> None:
    make_deliverable(project_name="foo", name="bar", description="d")
    out_path = tmp_path / "out.md"
    result = runner.invoke(app, ["design", "export", "--project", "foo", "-D", "bar", "-o", str(out_path)])
    assert result.exit_code == 0
    assert out_path.is_file()
    assert "bar" in out_path.read_text()
