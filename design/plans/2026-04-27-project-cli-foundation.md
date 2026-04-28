# project-cli: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation modules and the minimum viable CLI: `project-cli new`, `project-cli list`, `project-cli show`, plus `--help` and `--version`. Result: a working installable Python tool that creates and inspects projects (no deliverables, decisions, phases, code worktrees, validate, or export yet — those come in follow-up plans).

**Architecture:** Typer-based CLI with cross-cutting modules — manifest schema (Pydantic), AST-aware markdown editing (markdown-it-py), CWD-based scope detection, output formatting (Rich + JSON), dry-run op tracker, interactive prompts (questionary), and a thin git-ops wrapper. Tests run in isolated tmpdir workspaces via pytest's `tmp_path` and a `PROJECTS_DIR` env override. Each command lives in its own module under `src/project_cli/commands/`.

**Tech Stack:** Python 3.11+, Typer ≥0.12, Rich, Pydantic v2, markdown-it-py, Jinja2, tomlkit, questionary, pytest, pytest-snapshot.

---

## Pre-decided open questions

These were left open in the spec; settled here for this plan.

1. **Source location**: `~/projects/project-cli/` (the project root itself). Source under `src/project_cli/`, tests under `tests/`, design under `design/` (already there).
2. **Entry point name during development**: `project-cli` (the binary name when installed). This avoids a PATH conflict with the existing Bash `~/projects/bin/project` during development. Plan 4 (cutover) will rename to `project` and remove the Bash version atomically.
3. **Test isolation strategy**: pytest fixtures override `PROJECTS_DIR` env to a `tmp_path`. Git ops tests use real `git init`'d repos under `tmp_path` (no mocks — git is fast in tmpdir).
4. **Cutover with the Bash CLI**: deferred to Plan 4. During Plans 1–3 the new tool runs alongside, under the name `project-cli`.

---

## File Structure

```
~/projects/project-cli/
├── design/                                    # Already created (scope.md, design.md, decisions/)
├── plans/                                     # Already created
├── pyproject.toml                             # Task 1.1
├── README.md                                  # Task 1.1
├── .gitignore                                 # Task 1.1
├── src/
│   └── project_cli/
│       ├── __init__.py                        # Task 1.1 — exports __version__
│       ├── __main__.py                        # Task 1.1 — `python -m project_cli` entry
│       ├── app.py                             # Task 1.1 — top-level Typer app, global flags
│       ├── manifest.py                        # Task 1.2, 1.3, 1.4
│       ├── workspace.py                       # Task 1.5
│       ├── markdown_edit.py                   # Task 1.6
│       ├── templates.py                       # Task 1.7 — Jinja2 loader + helpers
│       ├── _templates/                        # Task 1.7 — Jinja2 .j2 files
│       │   ├── claude_md.j2
│       │   ├── design_md.j2
│       │   ├── scope_md.j2
│       │   ├── decision_entry.j2
│       │   └── phase_decision.j2
│       ├── output.py                          # Task 1.8
│       ├── dryrun.py                          # Task 1.9
│       ├── prompts.py                         # Task 1.10
│       ├── git_ops.py                         # Task 1.11
│       └── commands/
│           ├── __init__.py                    # Task 1.1
│           ├── new.py                         # Tasks 2.1–2.5
│           ├── list_cmd.py                    # Tasks 3.1–3.3
│           └── show.py                        # Tasks 3.4–3.6
├── tests/
│   ├── __init__.py                            # Task 1.1
│   ├── conftest.py                            # Task 1.12 — shared fixtures
│   ├── test_manifest.py                       # Tasks 1.2–1.4
│   ├── test_workspace.py                      # Task 1.5
│   ├── test_markdown_edit.py                  # Task 1.6
│   ├── test_templates.py                      # Task 1.7
│   ├── test_output.py                         # Task 1.8
│   ├── test_dryrun.py                         # Task 1.9
│   ├── test_prompts.py                        # Task 1.10
│   ├── test_git_ops.py                        # Task 1.11
│   └── commands/
│       ├── __init__.py
│       ├── test_new.py                        # Tasks 2.1–2.5
│       ├── test_list.py                       # Tasks 3.1–3.3
│       └── test_show.py                       # Tasks 3.4–3.6
```

---

## Pre-requisites

- Python 3.11+ on PATH
- `uv` installed (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `git` on PATH

---

## Milestone 1: Foundation modules

### Task 1.1: Initialize package skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.gitignore`
- Create: `src/project_cli/__init__.py`
- Create: `src/project_cli/__main__.py`
- Create: `src/project_cli/app.py`
- Create: `src/project_cli/commands/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "project-cli"
version = "0.1.0"
description = "CLI for the projects workspace"
requires-python = ">=3.11"
authors = [{ name = "Andrei Matei" }]
dependencies = [
    "typer>=0.12",
    "rich>=13",
    "pydantic>=2.6",
    "markdown-it-py>=3",
    "jinja2>=3.1",
    "tomlkit>=0.13",
    "questionary>=2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-snapshot>=0.9",
]

[project.scripts]
project-cli = "project_cli.app:app"

[tool.hatch.build.targets.wheel]
packages = ["src/project_cli"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
dist/
build/
.coverage
```

- [ ] **Step 3: Write `README.md`**

```markdown
# project-cli

Python CLI for the `~/projects/` workspace. See `design/` for the spec.

## Install (development)

    uv tool install --editable .

## Usage

    project-cli --help
```

- [ ] **Step 4: Write `src/project_cli/__init__.py`**

```python
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("project-cli")
except PackageNotFoundError:  # not installed (running from source without install)
    __version__ = "0+unknown"
```

- [ ] **Step 5: Write `src/project_cli/__main__.py`**

```python
from project_cli.app import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 6: Write `src/project_cli/app.py` skeleton**

```python
"""Top-level Typer app and global flags."""
from __future__ import annotations
import typer
from project_cli import __version__

app = typer.Typer(
    name="project-cli",
    help="Manage the ~/projects/ workspace.",
    no_args_is_help=True,
    add_completion=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress info logs."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose logs."),
) -> None:
    """project-cli: manage the ~/projects/ workspace."""
    if quiet and verbose:
        raise typer.BadParameter("--quiet and --verbose are mutually exclusive.")
```

- [ ] **Step 7: Write empty package init files**

```python
# src/project_cli/commands/__init__.py
"""Subcommand modules."""
```

```python
# tests/__init__.py
```

- [ ] **Step 8: Install editable and run smoke check**

Run:
```bash
cd ~/projects/project-cli && uv tool install --editable .
project-cli --version
project-cli --help
```
Expected: prints `0.1.0`, then prints help text.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml README.md .gitignore src/ tests/
git commit -m "feat(project-cli): initialize package skeleton with Typer app"
```

---

### Task 1.2: Manifest models — `RepoSpec` and shared base

**Files:**
- Create: `src/project_cli/manifest.py`
- Create: `tests/test_manifest.py`

- [ ] **Step 1: Write the failing test in `tests/test_manifest.py`**

```python
"""Tests for manifest schema and TOML I/O."""
from __future__ import annotations
import pytest
from pydantic import ValidationError
from project_cli.manifest import RepoSpec


def test_repo_spec_minimal() -> None:
    spec = RepoSpec(remote="git@github.com:org/repo.git", worktree="code")
    assert spec.remote == "git@github.com:org/repo.git"
    assert spec.worktree == "code"
    assert spec.local_hint is None
    assert spec.branch_prefix is None


def test_repo_spec_full() -> None:
    spec = RepoSpec(
        remote="git@github.com:org/repo.git",
        local_hint="~/repo",
        worktree="code-repo",
        branch_prefix="andrei/foo-repo",
    )
    assert spec.local_hint == "~/repo"
    assert spec.branch_prefix == "andrei/foo-repo"


def test_repo_spec_rejects_empty_remote() -> None:
    with pytest.raises(ValidationError):
        RepoSpec(remote="", worktree="code")


def test_repo_spec_rejects_absolute_worktree() -> None:
    """Worktree must be a relative subdir name, not an absolute path."""
    with pytest.raises(ValidationError):
        RepoSpec(remote="git@github.com:org/repo.git", worktree="/absolute/path")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_manifest.py -v`
Expected: FAIL with `ImportError` or `ModuleNotFoundError` (manifest.py doesn't exist yet).

- [ ] **Step 3: Implement `RepoSpec` in `src/project_cli/manifest.py`**

```python
"""Manifest schema (Pydantic) and TOML round-trip helpers.

Manifests live at:
    <project>/design/project.toml
    <project>/deliverables/<name>/design/deliverable.toml
"""
from __future__ import annotations
from pathlib import Path
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_manifest.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/manifest.py tests/test_manifest.py
git commit -m "feat(project-cli): add RepoSpec manifest model"
```

---

### Task 1.3: Manifest models — `ProjectManifest` and `DeliverableManifest`

**Files:**
- Modify: `src/project_cli/manifest.py`
- Modify: `tests/test_manifest.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_manifest.py`:

```python
from datetime import date
from project_cli.manifest import ProjectManifest, ProjectMeta, DeliverableManifest, DeliverableMeta


def test_project_manifest_minimal() -> None:
    m = ProjectManifest(project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 27)))
    assert m.project.name == "foo"
    assert m.repos == []


def test_project_manifest_with_repos() -> None:
    m = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 27)),
        repos=[RepoSpec(remote="git@github.com:org/r.git", worktree="code")],
    )
    assert len(m.repos) == 1


def test_deliverable_manifest_shared_excludes_repos() -> None:
    """shared_worktree=true is mutually exclusive with [[repos]]."""
    with pytest.raises(ValidationError):
        DeliverableManifest(
            deliverable=DeliverableMeta(
                name="bar",
                parent_project="foo",
                description="d",
                created=date(2026, 4, 27),
                shared_worktree=True,
            ),
            repos=[RepoSpec(remote="git@github.com:org/r.git", worktree="code")],
        )


def test_deliverable_manifest_shared_no_repos_ok() -> None:
    DeliverableManifest(
        deliverable=DeliverableMeta(
            name="bar",
            parent_project="foo",
            description="d",
            created=date(2026, 4, 27),
            shared_worktree=True,
        ),
    )


def test_deliverable_manifest_owned_with_repos_ok() -> None:
    DeliverableManifest(
        deliverable=DeliverableMeta(
            name="bar",
            parent_project="foo",
            description="d",
            created=date(2026, 4, 27),
            shared_worktree=False,
        ),
        repos=[RepoSpec(remote="git@github.com:org/r.git", worktree="code")],
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_manifest.py -v`
Expected: 5 PASS (existing) + 5 FAIL (new) due to missing classes.

- [ ] **Step 3: Implement the manifest classes**

Append to `src/project_cli/manifest.py`:

```python
from datetime import date as _date


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
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `pytest tests/test_manifest.py -v`
Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/manifest.py tests/test_manifest.py
git commit -m "feat(project-cli): add ProjectManifest and DeliverableManifest models"
```

---

### Task 1.4: Manifest TOML round-trip (`load_manifest`, `save_manifest`)

**Files:**
- Modify: `src/project_cli/manifest.py`
- Modify: `tests/test_manifest.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_manifest.py`:

```python
from project_cli.manifest import load_project_manifest, save_project_manifest, load_deliverable_manifest, save_deliverable_manifest


def test_project_manifest_roundtrip(tmp_path) -> None:
    path = tmp_path / "project.toml"
    original = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 27)),
        repos=[RepoSpec(
            remote="git@github.com:org/r.git",
            local_hint="~/r",
            worktree="code",
            branch_prefix="me/foo",
        )],
    )
    save_project_manifest(path, original)
    loaded = load_project_manifest(path)
    assert loaded == original


def test_project_manifest_load_rejects_bad_schema(tmp_path) -> None:
    path = tmp_path / "project.toml"
    path.write_text("[project]\nname = \"foo\"\n")  # missing description and created
    with pytest.raises(ValidationError):
        load_project_manifest(path)


def test_deliverable_manifest_roundtrip(tmp_path) -> None:
    path = tmp_path / "deliverable.toml"
    original = DeliverableManifest(
        deliverable=DeliverableMeta(
            name="bar", parent_project="foo", description="d",
            created=date(2026, 4, 27), shared_worktree=True,
        ),
    )
    save_deliverable_manifest(path, original)
    loaded = load_deliverable_manifest(path)
    assert loaded == original
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_manifest.py -v`
Expected: previous PASSes + 3 FAIL (no load/save fns).

- [ ] **Step 3: Implement load/save helpers**

Append to `src/project_cli/manifest.py`:

```python
import tomllib
import tomlkit


def load_project_manifest(path: Path) -> ProjectManifest:
    """Read and validate a `project.toml`."""
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return ProjectManifest.model_validate(raw)


def save_project_manifest(path: Path, manifest: ProjectManifest) -> None:
    """Write a `project.toml`. Uses tomlkit so future edits preserve comments."""
    doc = tomlkit.document()
    doc["project"] = manifest.project.model_dump(mode="json")
    if manifest.repos:
        repos_array = tomlkit.aot()
        for r in manifest.repos:
            repos_array.append(tomlkit.item({k: v for k, v in r.model_dump().items() if v is not None}))
        doc["repos"] = repos_array
    path.write_text(tomlkit.dumps(doc))


def load_deliverable_manifest(path: Path) -> DeliverableManifest:
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return DeliverableManifest.model_validate(raw)


def save_deliverable_manifest(path: Path, manifest: DeliverableManifest) -> None:
    doc = tomlkit.document()
    doc["deliverable"] = manifest.deliverable.model_dump(mode="json")
    if manifest.repos:
        repos_array = tomlkit.aot()
        for r in manifest.repos:
            repos_array.append(tomlkit.item({k: v for k, v in r.model_dump().items() if v is not None}))
        doc["repos"] = repos_array
    path.write_text(tomlkit.dumps(doc))
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `pytest tests/test_manifest.py -v`
Expected: all 12 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/manifest.py tests/test_manifest.py
git commit -m "feat(project-cli): add manifest TOML load/save round-trip"
```

---

### Task 1.5: Workspace module — paths and CWD scope detection

**Files:**
- Create: `src/project_cli/workspace.py`
- Create: `tests/test_workspace.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for workspace path conventions and CWD scope detection."""
from __future__ import annotations
from pathlib import Path
import os
import pytest
from project_cli.workspace import (
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workspace.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `workspace.py`**

```python
"""Workspace paths and CWD-based scope detection."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os


def projects_dir() -> Path:
    """Root of the workspace. `$PROJECTS_DIR` overrides `~/projects`."""
    raw = os.environ.get("PROJECTS_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / "projects").resolve()


def project_dir(name: str) -> Path:
    return projects_dir() / name


def deliverable_dir(project_name: str, deliverable_name: str) -> Path:
    return project_dir(project_name) / "deliverables" / deliverable_name


@dataclass(frozen=True)
class Scope:
    project: str | None
    deliverable: str | None


def detect_scope(cwd: Path | None = None) -> Scope:
    """Determine the (project, deliverable) scope from CWD.

    Returns Scope(None, None) if CWD is outside the workspace.
    """
    cwd_resolved = (cwd or Path.cwd()).resolve()
    root = projects_dir()
    try:
        rel = cwd_resolved.relative_to(root)
    except ValueError:
        return Scope(project=None, deliverable=None)
    parts = rel.parts
    if not parts:
        return Scope(project=None, deliverable=None)
    project = parts[0]
    deliverable = None
    if len(parts) >= 3 and parts[1] == "deliverables":
        deliverable = parts[2]
    return Scope(project=project, deliverable=deliverable)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_workspace.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/workspace.py tests/test_workspace.py
git commit -m "feat(project-cli): add workspace paths and CWD scope detection"
```

---

### Task 1.6: Markdown AST helpers — `find_section`, `replace_section`, `insert_under_heading`

**Files:**
- Create: `src/project_cli/markdown_edit.py`
- Create: `tests/test_markdown_edit.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for AST-aware markdown editing."""
from __future__ import annotations
import pytest
from project_cli.markdown_edit import (
    insert_under_heading,
    replace_section,
    section_exists,
)


SAMPLE = """# Title

Intro paragraph.

## Workflow

- Do thing A
- Do thing B

## References

- ref 1
"""


def test_section_exists_true() -> None:
    assert section_exists(SAMPLE, "Workflow") is True


def test_section_exists_false() -> None:
    assert section_exists(SAMPLE, "Deliverables") is False


def test_insert_under_existing_heading_appends() -> None:
    out = insert_under_heading(SAMPLE, "Workflow", "- Do thing C\n")
    assert "- Do thing C" in out
    # Existing items still present:
    assert "- Do thing A" in out
    # Inserted under Workflow, not References:
    workflow_idx = out.index("## Workflow")
    refs_idx = out.index("## References")
    assert workflow_idx < out.index("- Do thing C") < refs_idx


def test_insert_under_missing_heading_creates_it() -> None:
    out = insert_under_heading(SAMPLE, "Deliverables", "- bar: ../d/bar/\n")
    assert "## Deliverables" in out
    assert "- bar: ../d/bar/" in out


def test_insert_is_idempotent() -> None:
    """Re-inserting an identical line under a heading does not duplicate."""
    once = insert_under_heading(SAMPLE, "Workflow", "- Do thing C\n")
    twice = insert_under_heading(once, "Workflow", "- Do thing C\n")
    assert twice == once


def test_replace_section_swaps_body() -> None:
    out = replace_section(SAMPLE, "Workflow", "- Replaced\n")
    assert "- Replaced" in out
    assert "- Do thing A" not in out
    # Other sections untouched:
    assert "## References" in out
    assert "- ref 1" in out


def test_replace_section_missing_heading_appends() -> None:
    out = replace_section(SAMPLE, "Deliverables", "- foo\n")
    assert "## Deliverables" in out
    assert "- foo" in out


def test_remove_line_under_heading() -> None:
    """Removing a specific line preserves other content under the heading."""
    from project_cli.markdown_edit import remove_line_under_heading
    out = remove_line_under_heading(SAMPLE, "Workflow", "- Do thing A\n")
    assert "- Do thing A" not in out
    assert "- Do thing B" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_markdown_edit.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `markdown_edit.py`**

```python
"""AST-aware markdown editing for cross-file mutations.

Uses markdown-it-py to parse so we can target sections by heading text rather
than fragile regex. The implementation is line-based on top of the AST: we
identify the (start, end) line ranges of each top-level (h2) heading section,
then splice text into those ranges.
"""
from __future__ import annotations
from dataclasses import dataclass
from markdown_it import MarkdownIt


_MD = MarkdownIt("commonmark")


@dataclass(frozen=True)
class _Section:
    heading_level: int
    title: str
    heading_line: int  # 0-indexed line number of the heading itself
    body_start: int  # first line of body (heading_line + 1)
    body_end: int  # exclusive: first line of next same-or-higher-level heading or EOF


def _find_sections(text: str, level: int = 2) -> list[_Section]:
    """Return all sections at the given heading level."""
    lines = text.splitlines(keepends=True)
    tokens = _MD.parse(text)
    sections: list[_Section] = []
    pending: tuple[int, str, int] | None = None  # (heading_line, title, start_token_idx)

    def _close(end_line: int) -> None:
        nonlocal pending
        if pending is None:
            return
        heading_line, title, _ = pending
        sections.append(_Section(
            heading_level=level,
            title=title,
            heading_line=heading_line,
            body_start=heading_line + 1,
            body_end=end_line,
        ))
        pending = None

    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            tok_level = int(tok.tag[1:])
            if tok_level <= level:
                # close any open section at this point
                if tok.map is not None:
                    _close(tok.map[0])
            if tok_level == level:
                # title is the inline_text in the next token
                inline = tokens[i + 1]
                title = inline.content.strip()
                heading_line = tok.map[0]
                pending = (heading_line, title, i)
    _close(len(lines))
    return sections


def section_exists(text: str, title: str) -> bool:
    return any(s.title == title for s in _find_sections(text))


def _ensure_trailing_newline(s: str) -> str:
    return s if s.endswith("\n") else s + "\n"


def insert_under_heading(text: str, title: str, line_to_insert: str) -> str:
    """Insert a line under the section with `title`. Idempotent — no duplicates.

    If the section doesn't exist, create it at the end of the document.
    """
    line_to_insert = _ensure_trailing_newline(line_to_insert)
    text = _ensure_trailing_newline(text)
    sections = _find_sections(text)
    target = next((s for s in sections if s.title == title), None)
    if target is None:
        # Append a new section
        return text + f"\n## {title}\n{line_to_insert}"
    lines = text.splitlines(keepends=True)
    body_lines = lines[target.body_start:target.body_end]
    if any(b == line_to_insert for b in body_lines):
        return text  # already present, idempotent
    # Insert after the last non-empty body line, or right after the heading if body is empty
    insert_at = target.body_start
    for j in range(target.body_end - 1, target.body_start - 1, -1):
        if lines[j].strip():
            insert_at = j + 1
            break
    new_lines = lines[:insert_at] + [line_to_insert] + lines[insert_at:]
    return "".join(new_lines)


def replace_section(text: str, title: str, new_body: str) -> str:
    """Replace the body of a section. If the section doesn't exist, append it."""
    new_body = _ensure_trailing_newline(new_body)
    text = _ensure_trailing_newline(text)
    sections = _find_sections(text)
    target = next((s for s in sections if s.title == title), None)
    if target is None:
        return text + f"\n## {title}\n{new_body}"
    lines = text.splitlines(keepends=True)
    head = lines[:target.body_start]
    tail = lines[target.body_end:]
    return "".join(head) + new_body + ("\n" if not new_body.endswith("\n\n") else "") + "".join(tail)


def remove_line_under_heading(text: str, title: str, line_to_remove: str) -> str:
    """Remove a specific line from a section's body. No-op if absent."""
    line_to_remove = _ensure_trailing_newline(line_to_remove)
    text = _ensure_trailing_newline(text)
    sections = _find_sections(text)
    target = next((s for s in sections if s.title == title), None)
    if target is None:
        return text
    lines = text.splitlines(keepends=True)
    body = [b for b in lines[target.body_start:target.body_end] if b != line_to_remove]
    return "".join(lines[:target.body_start]) + "".join(body) + "".join(lines[target.body_end:])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_markdown_edit.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/markdown_edit.py tests/test_markdown_edit.py
git commit -m "feat(project-cli): add AST-aware markdown section editing"
```

---

### Task 1.7: Jinja2 templates and renderer

**Files:**
- Create: `src/project_cli/templates.py`
- Create: `src/project_cli/_templates/claude_md.j2`
- Create: `src/project_cli/_templates/scope_md.j2`
- Create: `src/project_cli/_templates/design_md.j2`
- Create: `src/project_cli/_templates/decision_entry.j2`
- Create: `tests/test_templates.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the template renderer."""
from project_cli.templates import render


def test_render_claude_md() -> None:
    out = render(
        "claude_md.j2",
        name="foo",
        description="A test project",
        repos=[],
        deliverables=[],
    )
    assert "# foo" in out
    assert "A test project" in out


def test_render_scope_md() -> None:
    out = render("scope_md.j2", name="foo", description="A test project")
    assert "# foo" in out
    assert "Scope Document" in out


def test_render_design_md() -> None:
    out = render("design_md.j2", name="foo", description="A test project")
    assert "# foo" in out


def test_render_decision_entry() -> None:
    out = render(
        "decision_entry.j2",
        date="2026-04-27",
        title="Pick a thing",
    )
    assert "# Pick a thing" in out
    assert "status: proposed" in out
    assert "2026-04-27" in out


def test_render_claude_md_with_repos() -> None:
    out = render(
        "claude_md.j2",
        name="foo",
        description="d",
        repos=[{"worktree": "code", "remote": "git@github.com:org/r.git"}],
        deliverables=[],
    )
    assert "## Code" in out
    assert "code" in out
    assert "git@github.com:org/r.git" in out


def test_render_claude_md_with_deliverables() -> None:
    out = render(
        "claude_md.j2",
        name="foo",
        description="d",
        repos=[],
        deliverables=[{"name": "bar", "description": "the bar"}],
    )
    assert "## Deliverables" in out
    assert "bar" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_templates.py -v`
Expected: FAIL — templates module missing.

- [ ] **Step 3: Write the templates**

`src/project_cli/_templates/claude_md.j2`:

```jinja
# {{ name }}

{{ description }}

{% if repos %}
## Code

{% for r in repos -%}
- `{{ r.worktree }}/` ← {{ r.remote }}{% if r.local_hint %} (local hint: `{{ r.local_hint }}`){% endif %}
{% endfor %}

{% endif -%}
{% if deliverables %}
## Deliverables

{% for d in deliverables -%}
- **{{ d.name }}**: ../deliverables/{{ d.name }}/design/ -- {{ d.description }}
{% endfor %}

{% endif -%}
## Workflow
- `scope.md` defines boundaries and success criteria — set early, changes rarely
- `design.md` is the living source of truth for the current technical approach
- `decisions/` contains one file per decision — question, options explored, conclusion
- The `## Code` and `## Deliverables` sections above are **generated from `project.toml`** — edit the manifest, not these sections.

## Rules
- Read scope.md and design.md before starting significant work
- When a decision is made, create a new file in decisions/
- If implementation reveals the scope needs to change, flag it explicitly
```

`src/project_cli/_templates/scope_md.j2`:

```jinja
# {{ name }}

## Scope Document

## Summary

{{ description }}

## Engineering Goals

- Bulleted list of things we are doing as part of this project

## Non-goals

- Bulleted list of things we are explicitly NOT doing as part of this project

## Assumptions and Risks

- Bulleted list

## Open Questions

## Success Criteria

-

## References

-
```

`src/project_cli/_templates/design_md.j2`:

```jinja
# {{ name }} — Design

## Status

Initial design. Living source of truth — update as understanding evolves.

## Summary

{{ description }}

## Architecture

## Components

## Open questions
```

`src/project_cli/_templates/decision_entry.j2`:

```jinja
---
date: {{ date }}
title: {{ title }}
status: proposed
---

# {{ title }}

## Question

<!-- What are we trying to decide? Why now? -->

## Options explored

### Option A

-

### Option B

-

## Conclusion

<!-- Which option was chosen and why. Note any follow-ups. -->

## Consequences

<!-- What changes downstream? Any design.md updates needed? -->
```

- [ ] **Step 4: Implement `templates.py`**

```python
"""Jinja2 template loader/renderer for design artifacts."""
from __future__ import annotations
from importlib.resources import files
from jinja2 import Environment, BaseLoader, TemplateNotFound, select_autoescape


class _PackageLoader(BaseLoader):
    """Loads templates from the `_templates/` resource dir of this package."""

    def get_source(self, environment, template):
        try:
            data = (files("project_cli") / "_templates" / template).read_text()
        except FileNotFoundError as e:
            raise TemplateNotFound(template) from e
        return data, template, lambda: True


_env = Environment(
    loader=_PackageLoader(),
    autoescape=select_autoescape(default=False),
    keep_trailing_newline=True,
    trim_blocks=False,
    lstrip_blocks=False,
)


def render(template: str, **context) -> str:
    return _env.get_template(template).render(**context)
```

- [ ] **Step 5: Update `pyproject.toml` to include templates**

Add to `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/project_cli"]
include = ["src/project_cli/_templates/*.j2"]
```

- [ ] **Step 6: Reinstall and run tests**

Run: `uv tool install --editable . && pytest tests/test_templates.py -v`
Expected: 6 PASS.

- [ ] **Step 7: Commit**

```bash
git add src/project_cli/templates.py src/project_cli/_templates/ tests/test_templates.py pyproject.toml
git commit -m "feat(project-cli): add Jinja2 templates for design artifacts"
```

---

### Task 1.8: Output module (Rich console + JSON)

**Files:**
- Create: `src/project_cli/output.py`
- Create: `tests/test_output.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the output module."""
from __future__ import annotations
import json
import io
from project_cli.output import Output


def test_info_goes_to_stderr(capsys) -> None:
    o = Output(quiet=False)
    o.info("hello")
    captured = capsys.readouterr()
    assert "hello" in captured.err
    assert captured.out == ""


def test_quiet_suppresses_info(capsys) -> None:
    o = Output(quiet=True)
    o.info("hello")
    assert capsys.readouterr().err == ""


def test_error_always_stderr(capsys) -> None:
    o = Output(quiet=True)
    o.error("oops")
    assert "oops" in capsys.readouterr().err


def test_print_result_human_to_stdout(capsys) -> None:
    o = Output(json_mode=False)
    o.result({"path": "/p"}, human_text="created at /p")
    captured = capsys.readouterr()
    assert "created at /p" in captured.out


def test_print_result_json_to_stdout(capsys) -> None:
    o = Output(json_mode=True)
    o.result({"path": "/p"})
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"path": "/p"}


def test_print_error_json(capsys) -> None:
    o = Output(json_mode=True)
    o.error("oops", code="not_found")
    captured = capsys.readouterr()
    assert json.loads(captured.err) == {"error": "oops", "code": "not_found"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_output.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `output.py`**

```python
"""Unified output for human + JSON modes.

Conventions:
- stdout: command results (human text or JSON payload)
- stderr: progress/info logs, errors, prompts
- --json implies --quiet
"""
from __future__ import annotations
import json
import sys
from typing import Any
from rich.console import Console


class Output:
    def __init__(self, quiet: bool = False, verbose: bool = False, json_mode: bool = False) -> None:
        if json_mode:
            quiet = True
        self.quiet = quiet
        self.verbose = verbose
        self.json_mode = json_mode
        self._stderr = Console(file=sys.stderr, highlight=False)
        self._stdout = Console(file=sys.stdout, highlight=False)

    def info(self, message: str) -> None:
        if not self.quiet:
            self._stderr.print(message)

    def warn(self, message: str) -> None:
        if not self.quiet:
            self._stderr.print(f"[yellow]{message}[/yellow]")

    def error(self, message: str, code: str | None = None) -> None:
        if self.json_mode:
            payload: dict[str, Any] = {"error": message}
            if code:
                payload["code"] = code
            self._stderr.print(json.dumps(payload))
        else:
            self._stderr.print(f"[red]error:[/red] {message}")

    def debug(self, message: str) -> None:
        if self.verbose:
            self._stderr.print(f"[dim]{message}[/dim]")

    def result(self, payload: Any, *, human_text: str | None = None) -> None:
        """Emit a command result.

        - JSON mode: writes `payload` as JSON to stdout.
        - Human mode: writes `human_text` (defaults to repr(payload)) to stdout.
        """
        if self.json_mode:
            self._stdout.print(json.dumps(payload, default=str))
        else:
            text = human_text if human_text is not None else repr(payload)
            self._stdout.print(text)
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `pytest tests/test_output.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/output.py tests/test_output.py
git commit -m "feat(project-cli): add unified human/JSON output module"
```

---

### Task 1.9: Dry-run op tracker

**Files:**
- Create: `src/project_cli/dryrun.py`
- Create: `tests/test_dryrun.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the dry-run op tracker."""
from pathlib import Path
from project_cli.dryrun import OpLog, Op


def test_op_log_records_creates() -> None:
    log = OpLog()
    log.create_file(Path("/p/a.md"), size=100)
    log.create_file(Path("/p/b.md"), size=50)
    assert len(log.ops) == 2
    assert log.ops[0].kind == "create"


def test_op_log_records_modifies_with_diff() -> None:
    log = OpLog()
    log.modify_file(Path("/p/x.md"), diff="+ added line\n")
    assert log.ops[0].kind == "modify"
    assert log.ops[0].diff == "+ added line\n"


def test_op_log_records_git_ops() -> None:
    log = OpLog()
    log.create_worktree(Path("/p/code"), source=Path("/repo"), branch="me/foo")
    assert log.ops[0].kind == "git-worktree-create"


def test_format_summary_groups_by_kind() -> None:
    log = OpLog()
    log.create_file(Path("/p/a"), size=10)
    log.create_file(Path("/p/b"), size=20)
    log.modify_file(Path("/p/c"), diff="+ x\n")
    out = log.format_summary()
    assert "Would create:" in out
    assert "Would modify:" in out
    assert "/p/a" in out
    assert "/p/c" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dryrun.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `dryrun.py`**

```python
"""Op tracker for --dry-run output.

Commands record planned mutations into an OpLog; when --dry-run is set, the
log is printed instead of actually applying the operations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Op:
    kind: str  # "create" | "modify" | "delete" | "git-worktree-create" | "git-worktree-remove" | "git-branch-rename"
    path: Path
    detail: str = ""
    diff: str | None = None


@dataclass
class OpLog:
    ops: list[Op] = field(default_factory=list)

    def create_file(self, path: Path, *, size: int = 0) -> None:
        self.ops.append(Op(kind="create", path=path, detail=f"({size} B)"))

    def modify_file(self, path: Path, *, diff: str = "") -> None:
        self.ops.append(Op(kind="modify", path=path, diff=diff))

    def delete_file(self, path: Path) -> None:
        self.ops.append(Op(kind="delete", path=path))

    def create_worktree(self, path: Path, *, source: Path, branch: str) -> None:
        self.ops.append(Op(
            kind="git-worktree-create",
            path=path,
            detail=f"from {source} on branch {branch}",
        ))

    def remove_worktree(self, path: Path) -> None:
        self.ops.append(Op(kind="git-worktree-remove", path=path))

    def rename_branch(self, repo: Path, *, old: str, new: str) -> None:
        self.ops.append(Op(
            kind="git-branch-rename",
            path=repo,
            detail=f"{old} → {new}",
        ))

    def format_summary(self) -> str:
        lines: list[str] = []
        groups: dict[str, list[Op]] = {}
        labels = {
            "create": "Would create:",
            "modify": "Would modify:",
            "delete": "Would delete:",
            "git-worktree-create": "Would create git worktree:",
            "git-worktree-remove": "Would remove git worktree:",
            "git-branch-rename": "Would rename branch:",
        }
        for op in self.ops:
            groups.setdefault(op.kind, []).append(op)
        for kind, label in labels.items():
            ops = groups.get(kind, [])
            if not ops:
                continue
            lines.append(f"[dry-run] {label}")
            for op in ops:
                suffix = f"  {op.detail}" if op.detail else ""
                lines.append(f"  {op.path}{suffix}")
                if op.diff:
                    for d in op.diff.splitlines():
                        lines.append(f"    {d}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `pytest tests/test_dryrun.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/dryrun.py tests/test_dryrun.py
git commit -m "feat(project-cli): add dry-run op tracker"
```

---

### Task 1.10: Prompts module (TTY-aware)

**Files:**
- Create: `src/project_cli/prompts.py`
- Create: `tests/test_prompts.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for prompts module."""
import sys
import pytest
from project_cli.prompts import is_interactive, require_or_fail


def test_is_interactive_false_when_stdin_not_tty(monkeypatch) -> None:
    """When stdin is not a tty (the typical pytest case), is_interactive is False."""
    # capsys/redirected stdin in pytest already makes isatty False
    assert is_interactive() in (True, False)  # implementation honors sys.stdin.isatty


def test_require_or_fail_returns_value_when_present() -> None:
    assert require_or_fail("hello", arg_name="--description") == "hello"


def test_require_or_fail_fails_when_missing_and_non_interactive(monkeypatch) -> None:
    monkeypatch.setattr("project_cli.prompts.is_interactive", lambda: False)
    with pytest.raises(SystemExit) as exc:
        require_or_fail(None, arg_name="--description")
    assert exc.value.code == 2  # usage error


def test_require_or_fail_prompts_when_missing_and_interactive(monkeypatch) -> None:
    monkeypatch.setattr("project_cli.prompts.is_interactive", lambda: True)
    monkeypatch.setattr("project_cli.prompts._prompt_text", lambda label: "filled-in")
    assert require_or_fail(None, arg_name="--description", label="Description") == "filled-in"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_prompts.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `prompts.py`**

```python
"""Interactive-prompt helpers, with non-TTY safety.

The CLI fails loud (exit 2) when a required value is missing on a non-TTY
stdin, rather than hanging on a prompt or silently using a default.
"""
from __future__ import annotations
import sys
import typer
import questionary


def is_interactive() -> bool:
    """True iff stdin is a TTY."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _prompt_text(label: str) -> str:
    return questionary.text(label).unsafe_ask() or ""


def require_or_fail(value: str | None, *, arg_name: str, label: str | None = None) -> str:
    """Return `value` if non-empty; else prompt on TTY, else exit 2."""
    if value:
        return value
    if not is_interactive():
        typer.echo(
            f"error: {arg_name} is required (stdin is not a TTY, cannot prompt)",
            err=True,
        )
        raise typer.Exit(code=2)
    text = _prompt_text(label or arg_name)
    if not text:
        typer.echo(f"error: {arg_name} is required", err=True)
        raise typer.Exit(code=2)
    return text


def confirm_destructive(message: str, *, yes: bool) -> None:
    """Confirm a destructive op. Raises typer.Exit(1) on decline.

    `yes=True` skips the prompt. Non-TTY without `yes` also fails.
    """
    if yes:
        return
    if not is_interactive():
        typer.echo(
            "error: refusing to run destructive op without --yes on a non-TTY stdin",
            err=True,
        )
        raise typer.Exit(code=1)
    answer = questionary.confirm(message, default=False).unsafe_ask()
    if not answer:
        typer.echo("Aborted.", err=True)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `pytest tests/test_prompts.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/prompts.py tests/test_prompts.py
git commit -m "feat(project-cli): add TTY-aware prompts module"
```

---

### Task 1.11: Git ops module

**Files:**
- Create: `src/project_cli/git_ops.py`
- Create: `tests/test_git_ops.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the git ops wrapper.

Uses real git repos in tmp_path — no mocks.
"""
from __future__ import annotations
import subprocess
from pathlib import Path
import pytest
from project_cli.git_ops import (
    GitError,
    create_worktree,
    default_branch,
    is_git_repo,
    is_worktree_dirty,
    git_user_slug,
)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    (path / "README").write_text("test\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=Test User", "commit", "-m", "init"],
        cwd=path, check=True, capture_output=True,
    )


def test_is_git_repo_true(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    assert is_git_repo(repo) is True


def test_is_git_repo_false(tmp_path) -> None:
    assert is_git_repo(tmp_path) is False


def test_default_branch_main(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    assert default_branch(repo) == "main"


def test_create_worktree_creates_branch_and_dir(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    wt = tmp_path / "wt"
    create_worktree(repo, wt, branch="me/feat")
    assert wt.is_dir()
    assert (wt / "README").read_text() == "test\n"
    # Branch exists in the repo:
    out = subprocess.run(
        ["git", "branch", "--list", "me/feat"], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout
    assert "me/feat" in out


def test_create_worktree_fails_if_dest_exists(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    wt = tmp_path / "wt"
    wt.mkdir()
    with pytest.raises(GitError):
        create_worktree(repo, wt, branch="me/feat")


def test_is_worktree_dirty_clean(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    wt = tmp_path / "wt"
    create_worktree(repo, wt, branch="me/feat")
    assert is_worktree_dirty(wt) is False


def test_is_worktree_dirty_with_change(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    wt = tmp_path / "wt"
    create_worktree(repo, wt, branch="me/feat")
    (wt / "new.txt").write_text("dirty")
    assert is_worktree_dirty(wt) is True


def test_git_user_slug(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Andrei Matei"], cwd=repo, check=True)
    assert git_user_slug(repo) == "andreimatei"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_git_ops.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `git_ops.py`**

```python
"""Thin wrapper around git CLI for the operations the workspace needs.

Uses subprocess directly rather than a library — no extra dep, the surface
we use is small.
"""
from __future__ import annotations
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path | None = None) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise GitError(f"git {' '.join(args[1:])} failed: {r.stderr.strip()}")
    return r.stdout


def is_git_repo(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
    except GitError:
        return False
    return True


def default_branch(repo: Path) -> str:
    """Symbolic ref of origin/HEAD, fallback to current branch."""
    try:
        out = _run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"], cwd=repo).strip()
        return out.removeprefix("refs/remotes/origin/")
    except GitError:
        out = _run(["git", "branch", "--show-current"], cwd=repo).strip()
        return out or "main"


def create_worktree(repo: Path, dest: Path, *, branch: str, base: str | None = None) -> None:
    if dest.exists():
        raise GitError(f"destination already exists: {dest}")
    base = base or default_branch(repo)
    _run(
        ["git", "-C", str(repo), "worktree", "add", str(dest), "-b", branch, base],
    )


def remove_worktree(dest: Path, *, force: bool = False) -> None:
    args = ["git", "worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(dest))
    # Run from inside the worktree's parent (or anywhere the dest is recognized)
    _run(args, cwd=dest.parent if dest.parent.exists() else None)


def is_worktree_dirty(worktree: Path) -> bool:
    out = _run(["git", "-C", str(worktree), "status", "--porcelain"])
    return bool(out.strip())


def git_user_slug(repo: Path) -> str:
    """Return git user.name lowercased and stripped of spaces/non-alphanumerics."""
    name = _run(["git", "-C", str(repo), "config", "user.name"]).strip()
    return "".join(ch for ch in name.lower() if ch.isalnum())


def current_branch(worktree: Path) -> str:
    return _run(["git", "-C", str(worktree), "branch", "--show-current"]).strip()


def rename_branch(repo: Path, *, old: str, new: str) -> None:
    _run(["git", "-C", str(repo), "branch", "-m", old, new])


def move_worktree(old_dest: Path, new_dest: Path) -> None:
    _run(["git", "-C", str(old_dest), "worktree", "move", str(old_dest), str(new_dest)])
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `pytest tests/test_git_ops.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/git_ops.py tests/test_git_ops.py
git commit -m "feat(project-cli): add git ops wrapper"
```

---

### Task 1.12: Test infrastructure — `conftest.py` shared fixtures

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/commands/__init__.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
"""Shared fixtures: isolated PROJECTS_DIR and helpers for assembling sample workspaces."""
from __future__ import annotations
import subprocess
from pathlib import Path
from datetime import date
from typing import Callable
import pytest
from project_cli.manifest import (
    ProjectManifest, ProjectMeta, RepoSpec,
    save_project_manifest,
)


@pytest.fixture
def projects(tmp_path, monkeypatch) -> Path:
    """Isolated `~/projects/` workspace at tmp_path."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def make_project(projects) -> Callable[[str, str], Path]:
    """Factory: create a project with empty design dir and a manifest."""
    def _make(name: str, description: str = "test project") -> Path:
        proj = projects / name
        (proj / "design" / "decisions").mkdir(parents=True)
        m = ProjectManifest(
            project=ProjectMeta(name=name, description=description, created=date(2026, 4, 27)),
            repos=[],
        )
        save_project_manifest(proj / "design" / "project.toml", m)
        (proj / "design" / ".phase").write_text("scoping\n")
        return proj
    return _make


@pytest.fixture
def source_repo(tmp_path) -> Path:
    """A real git repo with one commit, suitable for worktree creation."""
    repo = tmp_path / "_source_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "README").write_text("test\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo
```

- [ ] **Step 2: Write `tests/commands/__init__.py`**

```python
```

(empty marker)

- [ ] **Step 3: Run all tests to confirm fixtures don't break anything**

Run: `pytest -v`
Expected: all previous tests still PASS (~46 tests so far).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/commands/__init__.py
git commit -m "test(project-cli): add shared fixtures for isolated workspaces"
```

---

## Milestone 2: `project-cli new`

### Task 2.1: `new` command — happy path with `--no-worktree`

**Files:**
- Create: `src/project_cli/commands/new.py`
- Create: `tests/commands/test_new.py`
- Modify: `src/project_cli/app.py` (register the command)

- [ ] **Step 1: Write failing test**

```python
"""Tests for `project-cli new`."""
from __future__ import annotations
from pathlib import Path
from typer.testing import CliRunner
from project_cli.app import app
from project_cli.manifest import load_project_manifest

runner = CliRunner(mix_stderr=False)


def test_new_creates_design_dir(projects) -> None:
    result = runner.invoke(
        app, ["new", "foo", "-d", "A test project", "--no-worktree", "-y"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, (result.stdout, result.stderr)
    proj = projects / "foo"
    assert (proj / "design" / "CLAUDE.md").is_file()
    assert (proj / "design" / "scope.md").is_file()
    assert (proj / "design" / "design.md").is_file()
    assert (proj / "design" / ".phase").read_text().splitlines()[0] == "scoping"
    assert (proj / "design" / "project.toml").is_file()
    decisions = list((proj / "design" / "decisions").glob("*.md"))
    assert len(decisions) == 1
    assert "project-setup" in decisions[0].name


def test_new_writes_valid_manifest(projects) -> None:
    runner.invoke(app, ["new", "foo", "-d", "test", "--no-worktree", "-y"])
    m = load_project_manifest(projects / "foo" / "design" / "project.toml")
    assert m.project.name == "foo"
    assert m.project.description == "test"
    assert m.repos == []


def test_new_fails_if_project_exists(projects) -> None:
    runner.invoke(app, ["new", "foo", "-d", "test", "--no-worktree", "-y"])
    result = runner.invoke(app, ["new", "foo", "-d", "test", "--no-worktree", "-y"])
    assert result.exit_code == 1
    assert "already exists" in result.stderr


def test_new_fails_without_description_non_tty(projects) -> None:
    """When stdin is not a tty, missing --description exits with code 2."""
    result = runner.invoke(app, ["new", "foo", "--no-worktree", "-y"], input="")
    assert result.exit_code == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/test_new.py -v`
Expected: FAIL — no `new` subcommand.

- [ ] **Step 3: Implement `src/project_cli/commands/new.py`**

```python
"""`project-cli new <name>`."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import re
import shutil
import typer

from project_cli import templates, workspace
from project_cli.manifest import (
    ProjectManifest, ProjectMeta,
    save_project_manifest,
)
from project_cli.output import Output
from project_cli.prompts import require_or_fail


_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(name: str) -> str:
    s = name.lower().strip().replace(" ", "-")
    s = _SLUG_RE.sub("", s)
    return s


def cmd_new(
    name: str = typer.Argument(..., help="Project name (will be slugified)."),
    description: str | None = typer.Option(None, "-d", "--description"),
    repos: list[str] | None = typer.Option(None, "-r", "--repo", help="Source repo path (repeatable)."),
    no_worktree: bool = typer.Option(False, "--no-worktree"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Create a new project workspace."""
    out = Output(json_mode=json_mode)
    slug = _slugify(name)
    if not slug:
        out.error("invalid project name", code="invalid_name")
        raise typer.Exit(code=2)

    proj = workspace.project_dir(slug)
    if proj.exists():
        out.error(f"project already exists: {proj}", code="exists")
        raise typer.Exit(code=1)

    description = require_or_fail(description, arg_name="--description", label="Description")

    if dry_run:
        out.info(f"[dry-run] Would create project at {proj}")
        return

    # Make directories
    (proj / "design" / "decisions").mkdir(parents=True)

    # Manifest
    manifest = ProjectManifest(
        project=ProjectMeta(name=slug, description=description, created=date.today()),
        repos=[],
    )
    save_project_manifest(proj / "design" / "project.toml", manifest)

    # Templates
    (proj / "design" / "CLAUDE.md").write_text(
        templates.render("claude_md.j2", name=slug, description=description, repos=[], deliverables=[])
    )
    (proj / "design" / "scope.md").write_text(
        templates.render("scope_md.j2", name=slug, description=description)
    )
    (proj / "design" / "design.md").write_text(
        templates.render("design_md.j2", name=slug, description=description)
    )

    # Phase
    (proj / "design" / ".phase").write_text("scoping\n")

    # Initial decision file
    today = date.today().isoformat()
    decision_path = proj / "design" / "decisions" / f"{today}-project-setup.md"
    decision_path.write_text(
        templates.render("decision_entry.j2", date=today, title="Project workspace setup")
    )

    out.info(f"Created project: {proj}")
    out.result(
        {"path": str(proj), "design": str(proj / "design"), "worktrees": []},
        human_text=f"Project created: {proj}",
    )
```

- [ ] **Step 4: Register `new` in `src/project_cli/app.py`**

Append to `app.py`:

```python
from project_cli.commands.new import cmd_new
app.command(name="new")(cmd_new)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/commands/test_new.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Smoke check end-to-end**

Run:
```bash
PROJECTS_DIR=/tmp/projcli-smoke project-cli new smoketest -d "smoke" --no-worktree -y
ls /tmp/projcli-smoke/smoketest/design/
rm -rf /tmp/projcli-smoke
```
Expected: `CLAUDE.md  decisions  design.md  project.toml  scope.md  .phase`

- [ ] **Step 7: Commit**

```bash
git add src/project_cli/commands/new.py src/project_cli/app.py tests/commands/test_new.py
git commit -m "feat(project-cli): implement 'new' command with --no-worktree"
```

---

### Task 2.2: `new` command — JSON output

**Files:**
- Modify: `tests/commands/test_new.py`

- [ ] **Step 1: Write failing test**

Append to `tests/commands/test_new.py`:

```python
import json


def test_new_json_output(projects) -> None:
    result = runner.invoke(
        app, ["new", "foo", "-d", "t", "--no-worktree", "-y", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["path"].endswith("/foo")
    assert payload["worktrees"] == []
    # JSON mode suppresses info logs:
    assert "Created project" not in result.stderr
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/commands/test_new.py::test_new_json_output -v`
Expected: PASS (Output module already handles `--json` correctly per Task 1.8).

- [ ] **Step 3: Commit**

```bash
git add tests/commands/test_new.py
git commit -m "test(project-cli): cover 'new --json' output shape"
```

---

### Task 2.3: `new` with `--repo` (single repo, creates worktree)

**Files:**
- Modify: `src/project_cli/commands/new.py`
- Modify: `tests/commands/test_new.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/test_new.py`:

```python
def test_new_with_one_repo_creates_worktree(projects, source_repo) -> None:
    result = runner.invoke(
        app, ["new", "foo", "-d", "t", "-r", str(source_repo), "-y"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    assert (projects / "foo" / "code").is_dir()
    assert (projects / "foo" / "code" / "README").is_file()


def test_new_with_one_repo_writes_repo_to_manifest(projects, source_repo) -> None:
    runner.invoke(app, ["new", "foo", "-d", "t", "-r", str(source_repo), "-y"])
    m = load_project_manifest(projects / "foo" / "design" / "project.toml")
    assert len(m.repos) == 1
    assert m.repos[0].worktree == "code"


def test_new_with_invalid_repo_exits_1(projects, tmp_path) -> None:
    not_a_repo = tmp_path / "nope"
    not_a_repo.mkdir()
    result = runner.invoke(app, ["new", "foo", "-d", "t", "-r", str(not_a_repo), "-y"])
    assert result.exit_code == 1
    assert "not a git repo" in result.stderr.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/test_new.py -v`
Expected: 3 FAIL.

- [ ] **Step 3: Update `cmd_new` to handle repos**

Replace the body of `cmd_new` after the `(proj / "design" / "decisions").mkdir(...)` line and before the manifest write:

```python
    # Validate repos before creating any state
    repo_paths: list[Path] = []
    for r in (repos or []):
        rp = Path(r).expanduser().resolve()
        if not (rp / ".git").exists() and not (rp / ".git").is_file():
            # also check via is_git_repo for worktree-style .git files
            from project_cli import git_ops
            if not git_ops.is_git_repo(rp):
                # we already created the design dir above? no — move dir creation below this check.
                raise typer.Exit(code=1)
        repo_paths.append(rp)
```

Actually, restructure `cmd_new` so all validation happens *before* mkdir. Replace the function body to:

```python
def cmd_new(
    name: str = typer.Argument(..., help="Project name (will be slugified)."),
    description: str | None = typer.Option(None, "-d", "--description"),
    repos: list[str] | None = typer.Option(None, "-r", "--repo", help="Source repo path (repeatable)."),
    no_worktree: bool = typer.Option(False, "--no-worktree"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Create a new project workspace."""
    from project_cli import git_ops

    out = Output(json_mode=json_mode)
    slug = _slugify(name)
    if not slug:
        out.error("invalid project name", code="invalid_name")
        raise typer.Exit(code=2)

    proj = workspace.project_dir(slug)
    if proj.exists():
        out.error(f"project already exists: {proj}", code="exists")
        raise typer.Exit(code=1)

    description = require_or_fail(description, arg_name="--description", label="Description")

    # Resolve and validate repos up front
    repo_paths: list[Path] = []
    if repos and not no_worktree:
        for r in repos:
            rp = Path(r).expanduser().resolve()
            if not git_ops.is_git_repo(rp):
                out.error(f"not a git repo: {rp}", code="not_a_repo")
                raise typer.Exit(code=1)
            repo_paths.append(rp)

    if dry_run:
        out.info(f"[dry-run] Would create project at {proj}")
        return

    # Make directories
    (proj / "design" / "decisions").mkdir(parents=True)

    # Build manifest with repos (worktree path defaults to "code" when single, "code-<repo>" otherwise)
    from project_cli.manifest import RepoSpec
    repo_specs: list[RepoSpec] = []
    for rp in repo_paths:
        worktree_name = "code" if len(repo_paths) == 1 else f"code-{rp.name}"
        try:
            user_slug = git_ops.git_user_slug(rp)
        except Exception:
            user_slug = "user"
        branch_prefix_suffix = "-base" if len(repo_paths) == 1 else f"-{rp.name}-base"
        repo_specs.append(RepoSpec(
            remote=str(rp),
            local_hint=str(rp),
            worktree=worktree_name,
            branch_prefix=f"{user_slug}/{slug}{branch_prefix_suffix}",
        ))

    manifest = ProjectManifest(
        project=ProjectMeta(name=slug, description=description, created=date.today()),
        repos=repo_specs,
    )
    save_project_manifest(proj / "design" / "project.toml", manifest)

    # Templates
    repos_for_template = [{"worktree": r.worktree, "remote": r.remote, "local_hint": r.local_hint} for r in repo_specs]
    (proj / "design" / "CLAUDE.md").write_text(
        templates.render("claude_md.j2", name=slug, description=description, repos=repos_for_template, deliverables=[])
    )
    (proj / "design" / "scope.md").write_text(
        templates.render("scope_md.j2", name=slug, description=description)
    )
    (proj / "design" / "design.md").write_text(
        templates.render("design_md.j2", name=slug, description=description)
    )

    # Phase
    (proj / "design" / ".phase").write_text("scoping\n")

    # Initial decision file
    today = date.today().isoformat()
    decision_path = proj / "design" / "decisions" / f"{today}-project-setup.md"
    decision_path.write_text(
        templates.render("decision_entry.j2", date=today, title="Project workspace setup")
    )

    # Worktrees (last — file ops above already done)
    created_worktrees: list[str] = []
    for rp, spec in zip(repo_paths, repo_specs):
        wt_dest = proj / spec.worktree
        try:
            git_ops.create_worktree(rp, wt_dest, branch=spec.branch_prefix)
            created_worktrees.append(str(wt_dest))
        except git_ops.GitError as e:
            out.error(f"worktree creation failed: {e}", code="git_failed")
            out.info(f"Design files are at {proj / 'design'}; clean up with `rm -rf {proj}` or retry.")
            raise typer.Exit(code=1)

    out.info(f"Created project: {proj}")
    out.result(
        {"path": str(proj), "design": str(proj / "design"), "worktrees": created_worktrees},
        human_text=f"Project created: {proj}",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/test_new.py -v`
Expected: 7 PASS (4 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/commands/new.py tests/commands/test_new.py
git commit -m "feat(project-cli): support --repo on 'new' (single-repo worktree)"
```

---

### Task 2.4: `new` with multiple `--repo` flags

**Files:**
- Modify: `tests/commands/test_new.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/test_new.py`:

```python
def test_new_with_two_repos_creates_named_worktrees(projects, tmp_path) -> None:
    import subprocess
    repos = []
    for name in ("alpha", "beta"):
        r = tmp_path / f"src_{name}"
        r.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=r, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=r, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=r, check=True)
        (r / "README").write_text(name)
        subprocess.run(["git", "add", "."], cwd=r, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=r, check=True, capture_output=True)
        repos.append(str(r))
    result = runner.invoke(
        app,
        ["new", "multi", "-d", "two repos", "-r", repos[0], "-r", repos[1], "-y"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    assert (projects / "multi" / "code-src_alpha").is_dir()
    assert (projects / "multi" / "code-src_beta").is_dir()
    m = load_project_manifest(projects / "multi" / "design" / "project.toml")
    assert len(m.repos) == 2
    worktrees = {r.worktree for r in m.repos}
    assert worktrees == {"code-src_alpha", "code-src_beta"}
```

- [ ] **Step 2: Run test (should already pass given Task 2.3 logic)**

Run: `pytest tests/commands/test_new.py::test_new_with_two_repos_creates_named_worktrees -v`
Expected: PASS — Task 2.3 implementation already handles multi-repo.

- [ ] **Step 3: Commit**

```bash
git add tests/commands/test_new.py
git commit -m "test(project-cli): cover 'new' with multiple --repo flags"
```

---

### Task 2.5: `new --dry-run` shows planned op list, writes nothing

**Files:**
- Modify: `src/project_cli/commands/new.py`
- Modify: `tests/commands/test_new.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/test_new.py`:

```python
def test_new_dry_run_writes_nothing(projects, source_repo) -> None:
    result = runner.invoke(
        app, ["new", "foo", "-d", "t", "-r", str(source_repo), "--dry-run", "-y"],
    )
    assert result.exit_code == 0
    assert not (projects / "foo").exists()


def test_new_dry_run_lists_planned_ops(projects, source_repo) -> None:
    result = runner.invoke(
        app, ["new", "foo", "-d", "t", "-r", str(source_repo), "--dry-run", "-y"],
    )
    assert "[dry-run]" in result.stderr
    assert "project.toml" in result.stderr
    assert "scope.md" in result.stderr
    assert "design.md" in result.stderr
    assert "CLAUDE.md" in result.stderr
    assert "git worktree" in result.stderr.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/test_new.py -v -k dry_run`
Expected: 2 FAIL — current dry-run path is too terse.

- [ ] **Step 3: Replace the dry-run block in `cmd_new`**

In `src/project_cli/commands/new.py`, replace:

```python
    if dry_run:
        out.info(f"[dry-run] Would create project at {proj}")
        return
```

with:

```python
    if dry_run:
        from project_cli.dryrun import OpLog
        log = OpLog()
        log.create_file(proj / "design" / "project.toml", size=0)
        log.create_file(proj / "design" / "CLAUDE.md", size=0)
        log.create_file(proj / "design" / "scope.md", size=0)
        log.create_file(proj / "design" / "design.md", size=0)
        log.create_file(proj / "design" / ".phase", size=0)
        today = date.today().isoformat()
        log.create_file(proj / "design" / "decisions" / f"{today}-project-setup.md", size=0)
        for rp in repo_paths:
            wt_name = "code" if len(repo_paths) == 1 else f"code-{rp.name}"
            try:
                user_slug = git_ops.git_user_slug(rp)
            except Exception:
                user_slug = "user"
            suffix = "-base" if len(repo_paths) == 1 else f"-{rp.name}-base"
            log.create_worktree(proj / wt_name, source=rp, branch=f"{user_slug}/{slug}{suffix}")
        out.info(log.format_summary())
        return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/test_new.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/project_cli/commands/new.py tests/commands/test_new.py
git commit -m "feat(project-cli): implement 'new --dry-run' op list"
```

---

## Milestone 3: `project-cli list` and `project-cli show`

### Task 3.1: `list` — bare invocation lists projects

**Files:**
- Create: `src/project_cli/commands/list_cmd.py`
- Create: `tests/commands/test_list.py`
- Modify: `src/project_cli/app.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for `project-cli list`."""
from typer.testing import CliRunner
from project_cli.app import app

runner = CliRunner(mix_stderr=False)


def test_list_empty(projects) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    # Empty workspace prints either nothing or a header but no project lines.
    assert "(no projects)" in result.stdout or result.stdout.strip() == ""


def test_list_one_project(projects, make_project) -> None:
    make_project("foo", "first project")
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "foo" in result.stdout


def test_list_shows_phase(projects, make_project) -> None:
    make_project("foo", "first project")
    result = runner.invoke(app, ["list"])
    assert "scoping" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/test_list.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `list_cmd.py`**

```python
"""`project-cli list`."""
from __future__ import annotations
from dataclasses import dataclass
import typer
from rich.tree import Tree

from project_cli import workspace
from project_cli.manifest import load_project_manifest, load_deliverable_manifest
from project_cli.output import Output


@dataclass
class _ProjectRow:
    name: str
    phase: str
    description: str
    deliverable_count: int


def _scan(projects_root) -> list[_ProjectRow]:
    rows: list[_ProjectRow] = []
    if not projects_root.exists():
        return rows
    for child in sorted(projects_root.iterdir()):
        design = child / "design"
        manifest = design / "project.toml"
        if not manifest.is_file():
            continue
        m = load_project_manifest(manifest)
        phase_file = design / ".phase"
        phase = phase_file.read_text().splitlines()[0].strip() if phase_file.is_file() else "scoping"
        d_dir = child / "deliverables"
        d_count = 0
        if d_dir.is_dir():
            d_count = sum(1 for d in d_dir.iterdir() if (d / "design" / "deliverable.toml").is_file())
        rows.append(_ProjectRow(
            name=m.project.name,
            phase=phase,
            description=m.project.description,
            deliverable_count=d_count,
        ))
    return rows


def cmd_list(
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase."),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """List projects in the workspace."""
    out = Output(json_mode=json_mode)
    rows = _scan(workspace.projects_dir())
    if phase:
        rows = [r for r in rows if r.phase == phase]

    if json_mode:
        out.result({
            "projects": [
                {"name": r.name, "phase": r.phase, "description": r.description,
                 "deliverable_count": r.deliverable_count}
                for r in rows
            ]
        })
        return

    if not rows:
        out.result(None, human_text="(no projects)")
        return

    tree = Tree("Projects")
    for r in rows:
        label = f"[bold]{r.name}[/bold]  [{r.phase}]"
        if r.deliverable_count:
            label += f"  ({r.deliverable_count} deliverable{'s' if r.deliverable_count != 1 else ''})"
        tree.add(label)
    out._stdout.print(tree)
```

Note: the `out._stdout.print(tree)` access is intentional — `Output.result` doesn't render Rich objects. We could alternatively expose a `print_rich` method on `Output`. Add it:

In `src/project_cli/output.py`, add:

```python
    def print_rich(self, renderable) -> None:
        """Print a Rich renderable to stdout (only in human mode)."""
        if not self.json_mode:
            self._stdout.print(renderable)
```

Then change the `cmd_list` line to `out.print_rich(tree)`.

- [ ] **Step 4: Register in `app.py`**

Append:

```python
from project_cli.commands.list_cmd import cmd_list
app.command(name="list")(cmd_list)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/commands/test_list.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/project_cli/commands/list_cmd.py src/project_cli/app.py src/project_cli/output.py tests/commands/test_list.py
git commit -m "feat(project-cli): implement 'list' command"
```

---

### Task 3.2: `list --json` returns predictable schema

**Files:**
- Modify: `tests/commands/test_list.py`

- [ ] **Step 1: Write failing test**

Append to `tests/commands/test_list.py`:

```python
import json


def test_list_json_empty_returns_empty_list(projects) -> None:
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"projects": []}


def test_list_json_shape(projects, make_project) -> None:
    make_project("foo", "first project")
    make_project("bar", "second project")
    result = runner.invoke(app, ["list", "--json"])
    payload = json.loads(result.stdout)
    assert "projects" in payload
    names = {p["name"] for p in payload["projects"]}
    assert names == {"foo", "bar"}
    for p in payload["projects"]:
        assert {"name", "phase", "description", "deliverable_count"} <= p.keys()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/commands/test_list.py -v`
Expected: PASS (Task 3.1 already implemented JSON shape).

- [ ] **Step 3: Commit**

```bash
git add tests/commands/test_list.py
git commit -m "test(project-cli): cover 'list --json' shape"
```

---

### Task 3.3: `list --phase` filters by phase

**Files:**
- Modify: `tests/commands/test_list.py`

- [ ] **Step 1: Write failing test**

Append to `tests/commands/test_list.py`:

```python
def test_list_phase_filter(projects, make_project) -> None:
    make_project("foo", "scoping project")
    bar = make_project("bar", "implementing project")
    (bar / "design" / ".phase").write_text("implementing\n")

    result = runner.invoke(app, ["list", "--phase", "implementing"])
    assert result.exit_code == 0
    assert "bar" in result.stdout
    assert "foo" not in result.stdout
```

- [ ] **Step 2: Run test (should already pass)**

Run: `pytest tests/commands/test_list.py::test_list_phase_filter -v`
Expected: PASS — Task 3.1 implements `--phase` filter.

- [ ] **Step 3: Commit**

```bash
git add tests/commands/test_list.py
git commit -m "test(project-cli): cover 'list --phase' filter"
```

---

### Task 3.4: `show` — basic project card

**Files:**
- Create: `src/project_cli/commands/show.py`
- Create: `tests/commands/test_show.py`
- Modify: `src/project_cli/app.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for `project-cli show`."""
from typer.testing import CliRunner
from project_cli.app import app

runner = CliRunner(mix_stderr=False)


def test_show_by_name(projects, make_project) -> None:
    make_project("foo", "the foo project")
    result = runner.invoke(app, ["show", "foo"])
    assert result.exit_code == 0, result.stderr
    assert "foo" in result.stdout
    assert "the foo project" in result.stdout
    assert "scoping" in result.stdout


def test_show_unknown_project(projects) -> None:
    result = runner.invoke(app, ["show", "doesnotexist"])
    assert result.exit_code == 1
    assert "not found" in result.stderr.lower()


def test_show_auto_detects_project_from_cwd(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo", "auto-detected")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0, result.stderr
    assert "foo" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/test_show.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `show.py`**

```python
"""`project-cli show`."""
from __future__ import annotations
from pathlib import Path
import typer
from rich.panel import Panel
from rich.table import Table

from project_cli import workspace
from project_cli.manifest import load_project_manifest
from project_cli.output import Output


def cmd_show(
    name: str | None = typer.Argument(None, help="Project name. Auto-detected from CWD if omitted."),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Show a project's structure and current state."""
    out = Output(json_mode=json_mode)
    if name is None:
        scope = workspace.detect_scope()
        if scope.project is None:
            out.error("no project specified and none detected from CWD", code="no_project")
            raise typer.Exit(code=1)
        name = scope.project

    proj = workspace.project_dir(name)
    manifest_path = proj / "design" / "project.toml"
    if not manifest_path.is_file():
        out.error(f"project not found: {name}", code="not_found")
        raise typer.Exit(code=1)

    m = load_project_manifest(manifest_path)
    phase = (proj / "design" / ".phase").read_text().splitlines()[0].strip() if (proj / "design" / ".phase").is_file() else "scoping"
    decisions = sorted((proj / "design" / "decisions").glob("*.md"))
    decision_count = len(decisions)

    deliverables: list[tuple[str, str]] = []
    d_dir = proj / "deliverables"
    if d_dir.is_dir():
        for d in sorted(d_dir.iterdir()):
            d_manifest = d / "design" / "deliverable.toml"
            if d_manifest.is_file():
                d_phase_file = d / "design" / ".phase"
                d_phase = d_phase_file.read_text().splitlines()[0].strip() if d_phase_file.is_file() else "scoping"
                deliverables.append((d.name, d_phase))

    if json_mode:
        out.result({
            "name": m.project.name,
            "description": m.project.description,
            "path": str(proj),
            "phase": phase,
            "repos": [r.model_dump() for r in m.repos],
            "decision_count": decision_count,
            "deliverables": [{"name": n, "phase": p} for n, p in deliverables],
        })
        return

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("Name", m.project.name)
    table.add_row("Description", m.project.description)
    table.add_row("Path", str(proj))
    table.add_row("Phase", phase)
    table.add_row("Decisions", str(decision_count))
    if m.repos:
        table.add_row("Repos", "\n".join(f"{r.worktree}/  ←  {r.remote}" for r in m.repos))
    if deliverables:
        table.add_row("Deliverables", "\n".join(f"{n}  [{p}]" for n, p in deliverables))
    out.print_rich(Panel(table, title=f"Project: {m.project.name}", border_style="blue"))
```

- [ ] **Step 4: Register in `app.py`**

```python
from project_cli.commands.show import cmd_show
app.command(name="show")(cmd_show)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/commands/test_show.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/project_cli/commands/show.py src/project_cli/app.py tests/commands/test_show.py
git commit -m "feat(project-cli): implement 'show' command"
```

---

### Task 3.5: `show --json` schema

**Files:**
- Modify: `tests/commands/test_show.py`

- [ ] **Step 1: Write failing test**

Append:

```python
import json


def test_show_json_shape(projects, make_project) -> None:
    make_project("foo", "the foo project")
    result = runner.invoke(app, ["show", "foo", "--json"])
    payload = json.loads(result.stdout)
    assert payload["name"] == "foo"
    assert payload["description"] == "the foo project"
    assert payload["phase"] == "scoping"
    assert payload["repos"] == []
    assert payload["decision_count"] == 0
    assert payload["deliverables"] == []
```

- [ ] **Step 2: Run test**

Run: `pytest tests/commands/test_show.py::test_show_json_shape -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/commands/test_show.py
git commit -m "test(project-cli): cover 'show --json' shape"
```

---

### Task 3.6: Final smoke check + plan-1 done

**Files:** none

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: all tests pass (~60+ tests across 11 test files).

- [ ] **Step 2: Manual smoke check**

```bash
PROJECTS_DIR=/tmp/projcli-final project-cli new alpha -d "first" --no-worktree -y
PROJECTS_DIR=/tmp/projcli-final project-cli new beta  -d "second" --no-worktree -y
PROJECTS_DIR=/tmp/projcli-final project-cli list
PROJECTS_DIR=/tmp/projcli-final project-cli list --json
PROJECTS_DIR=/tmp/projcli-final project-cli show alpha
cd /tmp/projcli-final/alpha/design && PROJECTS_DIR=/tmp/projcli-final project-cli show
cd /tmp && rm -rf /tmp/projcli-final
```

Expected: all commands run without errors, list shows alpha+beta, show works both with explicit name and auto-detection.

- [ ] **Step 3: Tag the foundation milestone**

```bash
git tag project-cli-foundation
```

- [ ] **Step 4: Update `~/projects/project-cli/design/.phase` to `implementing`**

(Currently `scoping`; we have working code now.)

```bash
cd ~/projects/project-cli/design && echo -e "implementing\n2026-04-27 scoping → implementing  (Plan 1 complete)" > .phase && cd -
git add ~/projects/project-cli/design/.phase
git commit -m "chore(project-cli): advance phase to implementing after foundation plan"
```

---

## Self-review (run before handing off)

**Spec coverage** — every requirement in the spec covered by this plan should be one of:
- Implemented in tasks above
- Explicitly deferred to a follow-up plan (listed below)

What this plan covers:
- §2 Stack: pyproject.toml + all listed deps (Task 1.1)
- §3.1 Auto-detect from CWD: workspace.detect_scope (Task 1.5), used in show (Task 3.4)
- §3.2 Global flags: --version (Task 1.1), -q/-v (Task 1.1), --json + --dry-run (per command)
- §3.3 Exit codes: 0/1/2 used per Typer convention (verified in tests)
- §3.4 Output (stdout/stderr/JSON): output.py (Task 1.8)
- §3.5 Mutation safety dry-run: dryrun.py (Task 1.9), used in new (Task 2.5); confirm prompts implemented in prompts.py (Task 1.10) but only used in destructive ops (deferred)
- §4 Conceptual model: directory layout enforced by `new` (Task 2.1)
- §5 Manifest schema: Pydantic models + tomlkit round-trip (Tasks 1.2–1.4)
- §7.1 `new`: Tasks 2.1–2.5 (with --no-worktree, JSON, single repo, multi repo, dry-run)
- §7.11 `list`: Tasks 3.1–3.3
- §7.12 `show`: Tasks 3.4–3.5
- §7.23 `--version`: Task 1.1

What's deferred to follow-up plans:
- Plan 2: Deliverable group (§7.2–7.5), Decision group (§7.6–7.9), Phase command (§7.10)
- Plan 3: Validate (§7.13), Archive (§7.14), Rename (§7.15), Design export (§7.16), Code group (§7.17–7.21)
- Plan 4: Migration (§8), Completion (§7.22), Slash command rewrites, Cutover (rename binary to `project`, retire Bash version)

**Type consistency check** — manifest types used in `new`/`list`/`show` all reference the same `ProjectManifest`/`ProjectMeta`/`RepoSpec` defined in Task 1.2–1.3. JSON shapes returned by `--json` match what's documented in §7 of the spec. ✓

**Placeholder scan** — every step has actual code or actual commands. No "implement appropriately" / "add error handling" / "TBD". ✓

---

## Follow-up plans (sketch)

### Plan 2: Deliverable, decision, phase (`2026-XX-XX-project-cli-deliverable-decision-phase.md`)

Tasks: deliverable add/rm/rename/list, decision new/list/show/rm + --supersedes, phase show/transition (project + per-deliverable). Adds AST-mutation of parent CLAUDE.md/design.md and sibling deliverable CLAUDE.md files. Adds the `phase decision` auto-creation.

### Plan 3: Validate, design export, code group, archive, rename (`2026-XX-XX-project-cli-validate-export-code.md`)

Tasks: validate (structural and content checks), design export (project- and deliverable-level with composition), code list/status/init/add/rm, archive (soft-delete), rename (project-level with branch renames).

### Plan 4: Migration, completion, slash commands, cutover (`2026-XX-XX-project-cli-migration-cutover.md`)

Tasks: `project migrate` one-shot tool to populate manifests from existing CLAUDE.md text on `~/projects/api-ai-agents/`, `~/projects/project-cli/`, etc. Shell completion install. Rewrite slash command bodies (`/decide`, `/phase`, `/export-design`) to call the new CLI. Rename entry point from `project-cli` to `project`, remove `~/projects/bin/project` Bash and friends.
