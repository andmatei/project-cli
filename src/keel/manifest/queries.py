"""Manifest query helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from keel.manifest.io import load_milestones_manifest, save_milestones_manifest
from keel.manifest.models import Milestone, MilestonesManifest, Task

if TYPE_CHECKING:
    from keel.workspace import Scope


def find_milestone(manifest: MilestonesManifest, id: str) -> Milestone | None:
    """Return the milestone with the given id, or None."""
    return next((m for m in manifest.milestones if m.id == id), None)


def find_task(manifest: MilestonesManifest, id: str) -> Task | None:
    """Return the task with the given id, or None."""
    return next((t for t in manifest.tasks if t.id == id), None)


@contextmanager
def edit_milestones(scope: "Scope") -> Iterator[MilestonesManifest]:
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
