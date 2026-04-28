"""Manifest schema (Pydantic) and TOML round-trip helpers.

Manifests live at:
    <project>/design/project.toml
    <project>/deliverables/<name>/design/deliverable.toml
"""

from __future__ import annotations

import tomllib
from datetime import date as _date
from pathlib import Path

import tomlkit
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepoSpec(BaseModel):
    """One linked source repo + its worktree under the project unit."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    remote: str = Field(min_length=1, description="Canonical git remote URL")
    local_hint: str | None = Field(
        default=None,
        description="Suggested local clone path on a fresh machine.",
    )
    worktree: str = Field(
        min_length=1,
        description="Subdir under the unit where the worktree lives.",
    )
    branch_prefix: str | None = Field(
        default=None,
        description="Prefix for branches created in this worktree.",
    )

    @field_validator("worktree")
    @classmethod
    def _worktree_relative(cls, v: str) -> str:
        if Path(v).is_absolute():
            raise ValueError("worktree must be a relative subdir name")
        return v


class ProjectMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    created: _date


class ProjectManifest(BaseModel):
    """Schema for `<project>/design/project.toml`."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectMeta
    repos: list[RepoSpec] = Field(default_factory=list)


class DeliverableMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    parent_project: str = Field(min_length=1)
    description: str = Field(min_length=1)
    created: _date
    shared_worktree: bool = False


class DeliverableManifest(BaseModel):
    """Schema for `<deliverable>/design/deliverable.toml`."""

    model_config = ConfigDict(extra="forbid")

    deliverable: DeliverableMeta
    repos: list[RepoSpec] = Field(default_factory=list)

    @field_validator("repos")
    @classmethod
    def _shared_excludes_repos(cls, v: list[RepoSpec], info) -> list[RepoSpec]:
        meta = info.data.get("deliverable")
        if meta is not None and meta.shared_worktree and v:
            raise ValueError("shared_worktree=true is mutually exclusive with [[repos]]")
        return v


def _dict_no_none(d: dict) -> dict:
    """Filter out None values from a dictionary."""
    return {k: v for k, v in d.items() if v is not None}


def load_project_manifest(path: Path) -> ProjectManifest:
    """Read and validate a `project.toml`."""
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return ProjectManifest.model_validate(raw)


def save_project_manifest(path: Path, manifest: ProjectManifest) -> None:
    """Write a `project.toml`. Uses tomlkit so future edits preserve comments."""
    doc = tomlkit.document()
    doc["project"] = _dict_no_none(manifest.project.model_dump())
    if manifest.repos:
        repos_array = tomlkit.aot()
        for r in manifest.repos:
            repos_array.append(tomlkit.item(_dict_no_none(r.model_dump())))
        doc["repos"] = repos_array
    path.write_text(tomlkit.dumps(doc))


def load_deliverable_manifest(path: Path) -> DeliverableManifest:
    """Read and validate a `deliverable.toml`."""
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return DeliverableManifest.model_validate(raw)


def save_deliverable_manifest(path: Path, manifest: DeliverableManifest) -> None:
    """Write a `deliverable.toml`. Uses tomlkit so future edits preserve comments."""
    doc = tomlkit.document()
    doc["deliverable"] = _dict_no_none(manifest.deliverable.model_dump())
    if manifest.repos:
        repos_array = tomlkit.aot()
        for r in manifest.repos:
            repos_array.append(tomlkit.item(_dict_no_none(r.model_dump())))
        doc["repos"] = repos_array
    path.write_text(tomlkit.dumps(doc))
