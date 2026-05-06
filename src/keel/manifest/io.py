"""Manifest TOML I/O helpers."""

import tomllib
from pathlib import Path

import tomlkit

from keel.manifest.models import (
    MilestonesManifest,
    ProjectManifest,
    ProjectMeta,
    RepoSpec,
    _deprecated_deliverable_warning,
)


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


def load_deliverable_manifest(path: Path) -> ProjectManifest:
    """DEPRECATED — reads a v0.0.x deliverable.toml and returns a ProjectManifest.

    Used only by `keel migrate` and `keel manifest validate`. Removed in a
    future 0.0.x once active workspaces are migrated.

    The legacy `[deliverable]` table is mapped to `[project]`. The
    `parent_project` field on the legacy schema is dropped — in the new
    layout, parent identity is path-derived.
    """
    _deprecated_deliverable_warning()
    with path.open("rb") as f:
        raw = tomllib.load(f)
    deliv = raw.get("deliverable", {})
    project_block = {
        "name": deliv["name"],
        "description": deliv["description"],
        "created": deliv["created"],
        "lifecycle": deliv.get("lifecycle", "default"),
        "shared_worktree": deliv.get("shared_worktree", False),
    }
    return ProjectManifest(
        project=ProjectMeta(**project_block),
        repos=[RepoSpec.model_validate(r) for r in raw.get("repos", [])],
        extensions=raw.get("extensions", {}),
    )


def save_deliverable_manifest(path: Path, manifest) -> None:
    """DEPRECATED — replaced by `save_project_manifest`. Removed in a future 0.0.x.

    Should not be called in new code. Kept only as a stub so existing imports
    don't break during the redesign rollout.
    """
    raise NotImplementedError(
        "save_deliverable_manifest is removed. Use save_project_manifest instead."
    )


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
