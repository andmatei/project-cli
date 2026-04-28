"""Tests for workspace path conventions and CWD scope detection."""
from __future__ import annotations
from pathlib import Path
import os
import pytest
from keel.workspace import (
    projects_dir,
    project_dir,
    deliverable_dir,
    detect_scope,
    Scope,
)


def test_projects_dir_default_is_home_projects(monkeypatch) -> None:
    monkeypatch.delenv("PROJECTS_DIR", raising=False)
    assert projects_dir() == Path.home() / "projects"


def test_projects_dir_honors_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    assert projects_dir() == tmp_path


def test_project_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    assert project_dir("foo") == tmp_path / "foo"


def test_deliverable_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    assert deliverable_dir("foo", "bar") == tmp_path / "foo" / "deliverables" / "bar"


def test_detect_scope_outside_projects(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path.parent)
    assert detect_scope() == Scope(project=None, deliverable=None)


def test_detect_scope_in_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "design").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "foo" / "design")
    assert detect_scope() == Scope(project="foo", deliverable=None)


def test_detect_scope_in_deliverable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "deliverables" / "bar" / "design").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "foo" / "deliverables" / "bar" / "design")
    assert detect_scope() == Scope(project="foo", deliverable="bar")


def test_detect_scope_in_project_subdir(monkeypatch, tmp_path) -> None:
    """Scope detection works from any subdir, not just design/."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "code").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "foo" / "code")
    assert detect_scope() == Scope(project="foo", deliverable=None)
