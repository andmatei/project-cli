"""Tests for `keel phase`."""
from typer.testing import CliRunner
from keel.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# T4.1: show mode
# ---------------------------------------------------------------------------

def test_phase_show_at_project(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["phase"])
    assert result.exit_code == 0
    assert "scoping" in result.stdout
    assert "foo" in result.stdout


def test_phase_show_at_deliverable(projects, make_deliverable, monkeypatch) -> None:
    deliv = make_deliverable(project_name="foo", name="bar", description="d")
    monkeypatch.chdir(deliv / "design")
    result = runner.invoke(app, ["phase"])
    assert result.exit_code == 0
    assert "scoping" in result.stdout


def test_phase_show_no_scope(projects, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["phase"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# T4.2: forward/backward transitions + auto decision
# ---------------------------------------------------------------------------

def test_phase_forward_transition(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["phase", "designing", "-m", "scope locked"])
    assert result.exit_code == 0
    phase_text = (proj / "design" / ".phase").read_text()
    assert phase_text.startswith("designing\n")
    # History line includes transition info:
    assert "scoping → designing" in phase_text or "scoping -> designing" in phase_text


def test_phase_transition_creates_decision_file(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["phase", "designing", "-m", "ready"])
    decisions = list((proj / "design" / "decisions").glob("*-phase-designing.md"))
    assert len(decisions) == 1


def test_phase_transition_no_decision(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["phase", "designing", "--no-decision"])
    decisions = list((proj / "design" / "decisions").glob("*-phase-designing.md"))
    assert len(decisions) == 0


def test_phase_invalid_phase(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["phase", "bogus"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# T4.3: --next shortcut
# ---------------------------------------------------------------------------

def test_phase_next_advances_one_step(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["phase", "--next"])
    assert result.exit_code == 0
    assert (proj / "design" / ".phase").read_text().startswith("designing\n")


def test_phase_next_at_end_of_lifecycle(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    (proj / "design" / ".phase").write_text("done\n")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["phase", "--next"])
    assert result.exit_code == 1
    assert "no phase after" in result.stderr.lower()
