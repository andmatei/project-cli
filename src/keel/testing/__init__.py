"""Pytest fixtures for keel and keel plugin authors.

Add this to your conftest.py or pytest config:

    pytest_plugins = ["keel.testing"]

Provides:
- `projects` — isolated PROJECTS_DIR at tmp_path
- `make_project` — factory creating a project with manifest + scaffold files
- `make_deliverable` — factory creating a deliverable inside a project
- `source_repo` — a real one-commit git repo at tmp_path/_source_repo
"""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from keel import templates
from keel.manifest import (
    DeliverableManifest,
    DeliverableMeta,
    ProjectManifest,
    ProjectMeta,
    save_deliverable_manifest,
    save_project_manifest,
)
from keel.ticketing.mock import MockProvider


@pytest.fixture
def projects(tmp_path, monkeypatch) -> Path:
    """Isolated `~/projects/` workspace at tmp_path."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def make_project(projects) -> Callable[..., Path]:
    """Factory: create a project with empty design dir, manifest, and rendered templates."""
    def _make(name: str = "foo", description: str = "test project") -> Path:
        proj = projects / name
        (proj / "design" / "decisions").mkdir(parents=True)
        m = ProjectManifest(
            project=ProjectMeta(name=name, description=description, created=date(2026, 4, 29)),
            repos=[],
        )
        save_project_manifest(proj / "design" / "project.toml", m)
        (proj / "design" / ".phase").write_text("scoping\n")
        (proj / "design" / "CLAUDE.md").write_text(
            templates.render("claude_md.j2", name=name, description=description, repos=[], deliverables=[])
        )
        (proj / "design" / "design.md").write_text(
            templates.render("design_md.j2", name=name, description=description)
        )
        (proj / "design" / "scope.md").write_text(
            templates.render("scope_md.j2", name=name, description=description)
        )
        return proj
    return _make


@pytest.fixture
def make_deliverable(make_project) -> Callable[..., Path]:
    """Factory: create a deliverable inside a (possibly new) project."""
    def _make(
        project_name: str = "foo",
        name: str = "bar",
        description: str = "test deliverable",
        shared_worktree: bool = False,
    ) -> Path:
        from keel import workspace
        if not workspace.project_exists(project_name):
            make_project(project_name)
        deliv = workspace.deliverable_dir(project_name, name)
        (deliv / "design" / "decisions").mkdir(parents=True)
        m = DeliverableManifest(
            deliverable=DeliverableMeta(
                name=name,
                parent_project=project_name,
                description=description,
                created=date(2026, 4, 29),
                shared_worktree=shared_worktree,
            ),
            repos=[],
        )
        save_deliverable_manifest(deliv / "design" / "deliverable.toml", m)
        (deliv / "design" / ".phase").write_text("scoping\n")
        return deliv
    return _make


@pytest.fixture
def source_repo(tmp_path) -> Path:
    """A real git repo with one commit, suitable for worktree creation."""
    repo = tmp_path / "_source_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "README").write_text("test\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.fixture
def mock_ticket_provider() -> MockProvider:
    """A fresh MockProvider instance for each test."""
    return MockProvider()
