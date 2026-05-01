"""Manifest Pydantic schemas."""

from __future__ import annotations

from datetime import date as _date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from keel.lifecycle import (
    DEFAULT_MILESTONE_STATE,
    DEFAULT_TASK_STATE,
    MILESTONE_STATES,
    TASK_STATES,
)


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
