"""Shared fixtures: isolated PROJECTS_DIR and helpers for assembling sample workspaces."""
from __future__ import annotations
import subprocess
from pathlib import Path
from datetime import date
from typing import Callable
import pytest
from keel.manifest import (
    ProjectManifest, ProjectMeta, RepoSpec,
    save_project_manifest,
)


@pytest.fixture
def projects(tmp_path, monkeypatch) -> Path:
    """Isolated `~/projects/` workspace at tmp_path."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def make_project(projects) -> Callable[[str, str], Path]:
    """Factory: create a project with empty design dir and a manifest."""
    def _make(name: str, description: str = "test project") -> Path:
        proj = projects / name
        (proj / "design" / "decisions").mkdir(parents=True)
        m = ProjectManifest(
            project=ProjectMeta(name=name, description=description, created=date(2026, 4, 27)),
            repos=[],
        )
        save_project_manifest(proj / "design" / "project.toml", m)
        (proj / "design" / ".phase").write_text("scoping\n")
        return proj
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
