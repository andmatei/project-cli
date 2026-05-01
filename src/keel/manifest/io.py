"""Manifest TOML I/O helpers."""

import tomllib
from pathlib import Path

import tomlkit

from keel.manifest.models import (
    DeliverableManifest,
    MilestonesManifest,
    ProjectManifest,
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
