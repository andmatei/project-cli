"""Tests for manifest schema and TOML I/O."""
from __future__ import annotations
import pytest
from pydantic import ValidationError
from project_cli.manifest import RepoSpec


def test_repo_spec_minimal() -> None:
    spec = RepoSpec(remote="git@github.com:org/repo.git", worktree="code")
    assert spec.remote == "git@github.com:org/repo.git"
    assert spec.worktree == "code"
    assert spec.local_hint is None
    assert spec.branch_prefix is None


def test_repo_spec_full() -> None:
    spec = RepoSpec(
        remote="git@github.com:org/repo.git",
        local_hint="~/repo",
        worktree="code-repo",
        branch_prefix="andrei/foo-repo",
    )
    assert spec.local_hint == "~/repo"
    assert spec.branch_prefix == "andrei/foo-repo"


def test_repo_spec_rejects_empty_remote() -> None:
    with pytest.raises(ValidationError):
        RepoSpec(remote="", worktree="code")


def test_repo_spec_rejects_absolute_worktree() -> None:
    """Worktree must be a relative subdir name, not an absolute path."""
    with pytest.raises(ValidationError):
        RepoSpec(remote="git@github.com:org/repo.git", worktree="/absolute/path")


from datetime import date
from project_cli.manifest import ProjectManifest, ProjectMeta, DeliverableManifest, DeliverableMeta


def test_project_manifest_minimal() -> None:
    m = ProjectManifest(project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 27)))
    assert m.project.name == "foo"
    assert m.repos == []


def test_project_manifest_with_repos() -> None:
    m = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 27)),
        repos=[RepoSpec(remote="git@github.com:org/r.git", worktree="code")],
    )
    assert len(m.repos) == 1


def test_deliverable_manifest_shared_excludes_repos() -> None:
    """shared_worktree=true is mutually exclusive with [[repos]]."""
    with pytest.raises(ValidationError):
        DeliverableManifest(
            deliverable=DeliverableMeta(
                name="bar",
                parent_project="foo",
                description="d",
                created=date(2026, 4, 27),
                shared_worktree=True,
            ),
            repos=[RepoSpec(remote="git@github.com:org/r.git", worktree="code")],
        )


def test_deliverable_manifest_shared_no_repos_ok() -> None:
    DeliverableManifest(
        deliverable=DeliverableMeta(
            name="bar",
            parent_project="foo",
            description="d",
            created=date(2026, 4, 27),
            shared_worktree=True,
        ),
    )


def test_deliverable_manifest_owned_with_repos_ok() -> None:
    DeliverableManifest(
        deliverable=DeliverableMeta(
            name="bar",
            parent_project="foo",
            description="d",
            created=date(2026, 4, 27),
            shared_worktree=False,
        ),
        repos=[RepoSpec(remote="git@github.com:org/r.git", worktree="code")],
    )


from project_cli.manifest import load_project_manifest, save_project_manifest, load_deliverable_manifest, save_deliverable_manifest


def test_project_manifest_roundtrip(tmp_path) -> None:
    path = tmp_path / "project.toml"
    original = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 27)),
        repos=[RepoSpec(
            remote="git@github.com:org/r.git",
            local_hint="~/r",
            worktree="code",
            branch_prefix="me/foo",
        )],
    )
    save_project_manifest(path, original)
    loaded = load_project_manifest(path)
    assert loaded == original
    # Lock on-disk format: native TOML date, not a quoted string
    text = path.read_text()
    assert "created = 2026-04-27" in text
    assert 'created = "2026-04-27"' not in text


def test_project_manifest_load_rejects_bad_schema(tmp_path) -> None:
    path = tmp_path / "project.toml"
    path.write_text("[project]\nname = \"foo\"\n")  # missing description and created
    with pytest.raises(ValidationError):
        load_project_manifest(path)


def test_deliverable_manifest_roundtrip(tmp_path) -> None:
    path = tmp_path / "deliverable.toml"
    original = DeliverableManifest(
        deliverable=DeliverableMeta(
            name="bar", parent_project="foo", description="d",
            created=date(2026, 4, 27), shared_worktree=True,
        ),
    )
    save_deliverable_manifest(path, original)
    loaded = load_deliverable_manifest(path)
    assert loaded == original
