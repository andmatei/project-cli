"""Tests for the template renderer."""

from keel.templates import render


def test_render_scope_md() -> None:
    out = render("scope_md.j2", name="foo", description="A test project")
    assert "# foo" in out
    assert "Scope Document" in out


def test_render_design_md() -> None:
    out = render("design_md.j2", name="foo", description="A test project")
    assert "# foo" in out


def test_render_decision_entry() -> None:
    out = render(
        "decision_entry.j2",
        date="2026-04-27",
        title="Pick a thing",
    )
    assert "# Pick a thing" in out
    assert "status: proposed" in out
    assert "2026-04-27" in out
