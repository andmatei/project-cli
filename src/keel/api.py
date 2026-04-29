"""Public API for keel and keel plugins.

Anything exported from this module is considered stable across minor releases.
Plugin authors should import only from `keel.api` (or `keel.testing` for fixtures).

Anything outside `keel.api` and `keel.testing` is internal and may change.
"""
from __future__ import annotations

from keel.dryrun import Op, OpLog
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
from keel.output import Output
from keel.prompts import confirm_destructive, is_interactive, require_or_fail
from keel.util import slugify
from keel.workspace import (
    Scope,
    decisions_dir,
    deliverable_dir,
    deliverable_exists,
    detect_scope,
    project_dir,
    project_exists,
    projects_dir,
    read_phase,
)

__all__ = [
    # Manifest
    "DeliverableManifest", "DeliverableMeta", "ProjectManifest", "ProjectMeta", "RepoSpec",
    "load_deliverable_manifest", "load_project_manifest",
    "save_deliverable_manifest", "save_project_manifest",
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
    "decisions_dir", "deliverable_dir", "deliverable_exists",
    "detect_scope", "project_dir", "project_exists", "projects_dir",
    "read_phase",
]
