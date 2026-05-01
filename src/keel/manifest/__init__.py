"""Manifest schemas, TOML I/O, and query helpers.

Split into three submodules:
- `models`: Pydantic schemas (RepoSpec, ProjectManifest, DeliverableManifest, Milestone, Task, MilestonesManifest)
- `io`: load/save functions
- `queries`: find_milestone, find_task, edit_milestones context manager

Re-exported here for backward compatibility — callers can `from keel.manifest import X`.
"""

from keel.manifest.io import (
    load_deliverable_manifest,
    load_milestones_manifest,
    load_project_manifest,
    save_deliverable_manifest,
    save_milestones_manifest,
    save_project_manifest,
)
from keel.manifest.models import (
    DeliverableManifest,
    DeliverableMeta,
    Milestone,
    MilestonesManifest,
    ProjectManifest,
    ProjectMeta,
    RepoSpec,
    Task,
)
from keel.manifest.queries import (
    edit_milestones,
    find_milestone,
    find_task,
    get_milestone,
    get_task,
)

__all__ = [
    "DeliverableManifest",
    "DeliverableMeta",
    "Milestone",
    "MilestonesManifest",
    "ProjectManifest",
    "ProjectMeta",
    "RepoSpec",
    "Task",
    "load_deliverable_manifest",
    "load_milestones_manifest",
    "load_project_manifest",
    "save_deliverable_manifest",
    "save_milestones_manifest",
    "save_project_manifest",
    "edit_milestones",
    "find_milestone",
    "find_task",
    "get_milestone",
    "get_task",
]
