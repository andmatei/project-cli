"""Tests for `keel code list`."""

import json
from datetime import date

from typer.testing import CliRunner

from keel.app import app
from keel.manifest import (
    ProjectManifest,
    ProjectMeta,
    RepoSpec,
    save_project_manifest,
)

runner = CliRunner()


def test_list_empty(projects, make_project) -> None:
    make_project("foo")
    result = runner.invoke(app, ["code", "list", "--project", "foo"])
    assert result.exit_code == 0


def test_list_one_repo(projects, make_project) -> None:
    proj = make_project("foo")
    m = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 29)),
        repos=[
            RepoSpec(
                remote="git@example.com:org/r.git",
                local_hint="~/r",
                worktree="code",
                branch_prefix="alice/foo",
            )
        ],
    )
    save_project_manifest(proj / "design" / "project.toml", m)
    result = runner.invoke(app, ["code", "list", "--project", "foo"])
    assert result.exit_code == 0
    assert "git@example.com:org/r.git" in result.stdout
    assert "code" in result.stdout


def test_list_json_shape(projects, make_project) -> None:
    proj = make_project("foo")
    m = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 29)),
        repos=[RepoSpec(remote="git@e.com:o/r.git", worktree="code", branch_prefix="a/foo")],
    )
    save_project_manifest(proj / "design" / "project.toml", m)
    result = runner.invoke(app, ["code", "list", "--project", "foo", "--json"])
    payload = json.loads(result.stdout)
    assert payload["repos"][0]["remote"] == "git@e.com:o/r.git"
    assert payload["repos"][0]["worktree"] == "code"


def test_list_at_deliverable_scope(projects, make_deliverable) -> None:
    deliv = make_deliverable(project_name="foo", name="bar", description="d")
    from keel.manifest import (
        DeliverableManifest,
        DeliverableMeta,
        RepoSpec,
        save_deliverable_manifest,
    )

    m = DeliverableManifest(
        deliverable=DeliverableMeta(
            name="bar",
            parent_project="foo",
            description="d",
            created=date(2026, 4, 29),
            shared_worktree=False,
        ),
        repos=[RepoSpec(remote="git@e.com:o/d.git", worktree="code", branch_prefix="a/foo-bar")],
    )
    save_deliverable_manifest(deliv / "design" / "deliverable.toml", m)
    result = runner.invoke(app, ["code", "list", "--project", "foo", "-D", "bar"])
    assert result.exit_code == 0
    assert "git@e.com:o/d.git" in result.stdout
