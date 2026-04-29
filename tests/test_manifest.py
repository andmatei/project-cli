"""Tests for manifest schema and TOML I/O."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from keel.manifest import (
    DeliverableManifest,
    DeliverableMeta,
    ProjectManifest,
    ProjectMeta,
    RepoSpec,
    load_deliverable_manifest,
    load_project_manifest,
    save_deliverable_manifest,
    save_project_manifest,
)


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


def test_project_manifest_roundtrip(tmp_path) -> None:
    path = tmp_path / "project.toml"
    original = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 27)),
        repos=[
            RepoSpec(
                remote="git@github.com:org/r.git",
                local_hint="~/r",
                worktree="code",
                branch_prefix="me/foo",
            )
        ],
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
    path.write_text('[project]\nname = "foo"\n')  # missing description and created
    with pytest.raises(ValidationError):
        load_project_manifest(path)


def test_deliverable_manifest_roundtrip(tmp_path) -> None:
    path = tmp_path / "deliverable.toml"
    original = DeliverableManifest(
        deliverable=DeliverableMeta(
            name="bar",
            parent_project="foo",
            description="d",
            created=date(2026, 4, 27),
            shared_worktree=True,
        ),
    )
    save_deliverable_manifest(path, original)
    loaded = load_deliverable_manifest(path)
    assert loaded == original


def test_repo_spec_rejects_worktree_with_slash() -> None:
    with pytest.raises(ValidationError):
        RepoSpec(remote="git@e.com:o/r.git", worktree="sub/dir")


def test_repo_spec_rejects_worktree_dotdot() -> None:
    with pytest.raises(ValidationError):
        RepoSpec(remote="git@e.com:o/r.git", worktree="..")


def test_repo_spec_rejects_worktree_dot() -> None:
    with pytest.raises(ValidationError):
        RepoSpec(remote="git@e.com:o/r.git", worktree=".")


def test_repo_spec_rejects_worktree_with_backslash() -> None:
    with pytest.raises(ValidationError):
        RepoSpec(remote="git@e.com:o/r.git", worktree=r"sub\dir")


def test_repo_spec_accepts_normal_name() -> None:
    s = RepoSpec(remote="git@e.com:o/r.git", worktree="code")
    assert s.worktree == "code"
    s2 = RepoSpec(remote="git@e.com:o/r.git", worktree="code-foo")
    assert s2.worktree == "code-foo"


def test_project_manifest_extensions_default_empty() -> None:
    m = ProjectManifest(project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 29)))
    assert m.extensions == {}


def test_project_manifest_extensions_round_trip(tmp_path) -> None:
    """Plugin-namespaced config under extensions survives load/save."""
    path = tmp_path / "project.toml"
    original = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 29)),
        extensions={
            "ticketing": {
                "jira": {
                    "instance_url": "https://example.atlassian.net",
                    "project_key": "FOO",
                    "epic_id": "FOO-1234",
                }
            }
        },
    )
    save_project_manifest(path, original)
    loaded = load_project_manifest(path)
    assert loaded.extensions["ticketing"]["jira"]["epic_id"] == "FOO-1234"
    assert loaded.extensions == original.extensions


def test_project_manifest_unknown_top_level_still_rejected(tmp_path) -> None:
    """extra='forbid' still rejects unknown top-level keys (only `extensions` is open)."""
    path = tmp_path / "bad.toml"
    path.write_text(
        '[project]\nname = "foo"\ndescription = "d"\ncreated = 2026-04-29\n'
        '[bogus]\nfoo = "bar"\n'
    )
    with pytest.raises(ValidationError):
        load_project_manifest(path)


def test_deliverable_manifest_extensions_round_trip(tmp_path) -> None:
    path = tmp_path / "deliverable.toml"
    original = DeliverableManifest(
        deliverable=DeliverableMeta(
            name="bar", parent_project="foo", description="d",
            created=date(2026, 4, 29), shared_worktree=False,
        ),
        extensions={"ticketing": {"jira": {"story_id": "FOO-1235"}}},
    )
    save_deliverable_manifest(path, original)
    loaded = load_deliverable_manifest(path)
    assert loaded.extensions == original.extensions
