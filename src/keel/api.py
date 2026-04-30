"""Public API for keel and keel plugins.

Anything exported from this module is considered stable across minor releases.
Plugin authors should import only from `keel.api` (or `keel.testing` for fixtures).

Anything outside `keel.api` and `keel.testing` is internal and may change.
"""
from __future__ import annotations

from keel.dryrun import Op, OpLog
from keel.lifecycle import (
    DEFAULT_MILESTONE_STATE,
    DEFAULT_TASK_STATE,
    MILESTONE_STATES,
    TASK_STATES,
    is_terminal_milestone_state,
    is_terminal_task_state,
    is_valid_milestone_state,
    is_valid_task_state,
)
from keel.manifest import (
    DeliverableManifest,
    DeliverableMeta,
    Milestone,
    MilestonesManifest,
    ProjectManifest,
    ProjectMeta,
    RepoSpec,
    Task,
    load_deliverable_manifest,
    load_milestones_manifest,
    load_project_manifest,
    save_deliverable_manifest,
    save_milestones_manifest,
    save_project_manifest,
)
from keel.milestones import (
    GraphError,
    blocked_tasks,
    ready_tasks,
    topological_sort,
    validate_dag,
)
from keel.output import Output
from keel.prompts import confirm_destructive, is_interactive, require_or_fail
from keel.ticketing import get_provider_for_project
from keel.ticketing.base import Ticket, TicketProvider
from keel.ticketing.registry import list_providers, load_provider
from keel.util import slugify
from keel.workspace import (
    Scope,
    decisions_dir,
    deliverable_dir,
    deliverable_exists,
    design_dir,
    detect_scope,
    manifest_path,
    milestones_manifest_path,
    phase_file,
    project_dir,
    project_exists,
    projects_dir,
    read_phase,
)

__all__ = [
    # Lifecycle
    "DEFAULT_MILESTONE_STATE", "DEFAULT_TASK_STATE",
    "MILESTONE_STATES", "TASK_STATES",
    "is_terminal_milestone_state", "is_terminal_task_state",
    "is_valid_milestone_state", "is_valid_task_state",
    # Manifest
    "DeliverableManifest", "DeliverableMeta", "Milestone", "MilestonesManifest",
    "ProjectManifest", "ProjectMeta", "RepoSpec", "Task",
    "load_deliverable_manifest", "load_milestones_manifest", "load_project_manifest",
    "save_deliverable_manifest", "save_milestones_manifest", "save_project_manifest",
    # Milestones graph helpers
    "GraphError", "blocked_tasks", "ready_tasks", "topological_sort", "validate_dag",
    # Dryrun
    "Op", "OpLog",
    # Output
    "Output",
    # Prompts
    "confirm_destructive", "is_interactive", "require_or_fail",
    # Util
    "slugify",
    # Workspace
    "Scope",
    "decisions_dir", "design_dir", "deliverable_dir", "deliverable_exists",
    "detect_scope", "manifest_path", "milestones_manifest_path", "phase_file",
    "project_dir", "project_exists", "projects_dir",
    "read_phase",
    # Ticketing
    "Ticket", "TicketProvider", "get_provider_for_project", "list_providers", "load_provider",
]
