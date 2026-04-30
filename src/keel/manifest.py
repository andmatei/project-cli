"""Manifest schema (Pydantic) and TOML round-trip helpers.

Manifests live at:
    <project>/design/project.toml
    <project>/deliverables/<name>/design/deliverable.toml
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date as _date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomlkit
from pydantic import BaseModel, ConfigDict, Field, field_validator

from keel.lifecycle import (
    DEFAULT_MILESTONE_STATE,
    DEFAULT_TASK_STATE,
    MILESTONE_STATES,
    TASK_STATES,
)

if TYPE_CHECKING:
    from keel.workspace import Scope


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
    def _worktree_single_component(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("worktree must be a non-empty string")
        if "/" in v or "\\" in v:
            raise ValueError("worktree must be a single path component (no slashes)")
        if v in (".", ".."):
            raise ValueError("worktree must not be '.' or '..'")
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
    extensions: dict[str, Any] = Field(
        default_factory=dict,
        description="Plugin-namespaced config. Plugins read keys under their own namespace, e.g. extensions['ticketing']['jira'].",
    )


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
    extensions: dict[str, Any] = Field(default_factory=dict)

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
    if manifest.extensions:
        doc["extensions"] = tomlkit.item(manifest.extensions)
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
    if manifest.extensions:
        doc["extensions"] = tomlkit.item(manifest.extensions)
    path.write_text(tomlkit.dumps(doc))


class Milestone(BaseModel):
    """A grouping of related implementation work, scoped to the `implementing` phase."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(
        min_length=1, description="Stable identifier within the unit (e.g. 'm1', 'foundation')."
    )
    title: str = Field(min_length=1)
    description: str = ""
    status: str = Field(default=DEFAULT_MILESTONE_STATE)
    fan_out: list[str] = Field(
        default_factory=list, description="Deliverable names this milestone fans out to."
    )
    parent: str | None = Field(
        default=None,
        description="If this is a sub-milestone, the parent milestone's id at the project level.",
    )
    ticket_id: str | None = Field(
        default=None, description="Provider-issued ticket id (e.g., Jira issue key)."
    )

    @field_validator("status")
    @classmethod
    def _status_in_set(cls, v: str) -> str:
        if v not in MILESTONE_STATES:
            raise ValueError(f"status must be one of {MILESTONE_STATES}")
        return v


class Task(BaseModel):
    """An atomic unit of work under a milestone."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    milestone: str = Field(min_length=1, description="The owning milestone's id.")
    title: str = Field(min_length=1)
    description: str = ""
    status: str = Field(default=DEFAULT_TASK_STATE)
    depends_on: list[str] = Field(
        default_factory=list, description="Other task ids that must be done before this can start."
    )
    branch: str | None = Field(
        default=None, description="Git branch for this task. Auto-set when started."
    )
    ticket_id: str | None = Field(
        default=None, description="Provider-issued ticket id (e.g., Jira issue key)."
    )

    @field_validator("status")
    @classmethod
    def _status_in_set(cls, v: str) -> str:
        if v not in TASK_STATES:
            raise ValueError(f"status must be one of {TASK_STATES}")
        return v


class MilestonesManifest(BaseModel):
    """Schema for `<unit>/design/milestones.toml`."""

    model_config = ConfigDict(extra="forbid")

    milestones: list[Milestone] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)


def find_milestone(manifest: MilestonesManifest, id: str) -> Milestone | None:
    """Return the milestone with the given id, or None."""
    return next((m for m in manifest.milestones if m.id == id), None)


def find_task(manifest: MilestonesManifest, id: str) -> Task | None:
    """Return the task with the given id, or None."""
    return next((t for t in manifest.tasks if t.id == id), None)


@contextmanager
def edit_milestones(scope: Scope) -> Iterator[MilestonesManifest]:
    """Load → yield → save the milestones manifest at the scope's path.

    Usage:
        with edit_milestones(scope) as manifest:
            # mutate manifest in place
    """
    path = scope.milestones_manifest_path
    manifest = load_milestones_manifest(path)
    yield manifest
    path.parent.mkdir(parents=True, exist_ok=True)
    save_milestones_manifest(path, manifest)


def load_milestones_manifest(path: Path) -> MilestonesManifest:
    """Read and validate `milestones.toml`. Returns an empty manifest if the file doesn't exist."""
    if not path.is_file():
        return MilestonesManifest()
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return MilestonesManifest.model_validate(raw)


def save_milestones_manifest(path: Path, manifest: MilestonesManifest) -> None:
    """Write a `milestones.toml`. Uses tomlkit so future edits preserve comments."""
    doc = tomlkit.document()
    if manifest.milestones:
        ms_array = tomlkit.aot()
        for m in manifest.milestones:
            ms_array.append(tomlkit.item(_dict_no_none(m.model_dump())))
        doc["milestones"] = ms_array
    if manifest.tasks:
        ts_array = tomlkit.aot()
        for t in manifest.tasks:
            ts_array.append(tomlkit.item(_dict_no_none(t.model_dump())))
        doc["tasks"] = ts_array
    path.write_text(tomlkit.dumps(doc))
