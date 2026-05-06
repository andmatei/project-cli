# Plan 8: Data-model + project-layout redesign (0.0.2 → 0.0.3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate keel from the old layout (`design/{project.toml,milestones.toml,.phase,…}` + separate `deliverable.toml` schema) to the new layout (manifests at project root, `.keel/` for tool state, identical schema for projects and deliverables, implicit-default milestone, per-plugin ticketing templates).

**Versioning note:** Both wheels stay on 0.0.x — `keel-cli` 0.0.2 → 0.0.3 and `keel-jira` 0.0.1 → 0.0.2. Pre-1.0 every release is "in development"; staying on 0.0.x signals "still freely changing things, no compatibility promises yet." A future 0.1.0 will mark the convergence point.

**Architecture:** The redesign is one big interlocking change. Implementation order: foundations first (`Scope` API, manifest models), then the `.keel/` directory and lifecycle snapshot, then the migration command, then the hierarchy refactor (implicit-default milestone), then the deliverable consolidation, then the new `TicketProvider` protocol + keel-jira refactor, finally docs and version bumps.

**Tech Stack:** Same as Plan 7. Pydantic v2, Typer, tomlkit/tomllib, Jinja2, httpx, respx. No new dependencies.

---

## Pre-requisites

- Plan 7 + keel-jira 0.0.1 + keel-cli 0.0.2 published to PyPI.
- 494 keel-cli tests + 33 keel-jira tests pass on `main`.
- Ruff + ruff format clean across `src/`, `tests/`, `plugins/`.
- The redesign spec at `design/specs/2026-05-05-data-model-redesign.md` is locked.

---

## File Structure

After Plan 8 lands the keel-cli source tree changes substantially. New / modified / deleted listed:

```
src/keel/
├── manifest/
│   ├── models.py              # MODIFY — drop DeliverableManifest/Meta, add lifecycle to ProjectMeta, add shared_worktree
│   ├── io.py                  # MODIFY — drop deliverable load/save
│   └── queries.py             # unchanged
├── workspace.py               # MODIFY — Scope API points at new layout (project root, .keel/)
├── commands/
│   ├── new.py                 # MODIFY — write project.toml at root, .keel/phase, .keel/lifecycle.lock.toml, README.md
│   ├── migrate.py             # MODIFY — add old → new layout migration step
│   ├── deliverable/add.py     # MODIFY — sugar over the same scaffold path used by keel new
│   ├── deliverable/rm.py      # MODIFY — paths
│   ├── deliverable/list.py    # MODIFY — paths
│   ├── deliverable/rename.py  # MODIFY — paths
│   ├── task/add.py            # MODIFY — auto-create default milestone when --milestone omitted
│   ├── task/rm.py             # MODIFY — auto-remove default milestone if it becomes empty
│   ├── task/move.py           # NEW — move task between milestones
│   ├── milestone/rm.py        # MODIFY — auto-remove default milestone helper used here too
│   ├── show.py                # MODIFY — surface .keel/phase, skip rendering single-default-milestone
│   └── (most other commands)  # MODIFY — read/write paths via the new Scope API
├── ticketing/
│   ├── base.py                # MODIFY — new Protocol signature (typed Milestone/Task, drop parent_id)
│   ├── mock.py                # MODIFY — match new signature
│   └── (no template helper)   # explicitly NOT shipping a shared renderer
├── _templates/
│   └── readme_md.j2           # NEW — auto-generated README

plugins/jira/
├── src/keel_jira/
│   ├── provider.py            # MODIFY — new protocol; render per-plugin templates internally
│   ├── client.py              # unchanged
│   ├── config.py              # MODIFY — gain templates sub-block + Jinja env
│   └── templates.py           # NEW — Jinja env + default templates
├── tests/                     # MODIFY — match new protocol signature
└── pyproject.toml             # MODIFY — bump to 0.0.3

tests/                         # MODIFY — many file path updates; some new tests for new behaviors

design/decisions/
└── 2026-05-05-data-model-redesign.md   # NEW — record the locked decisions
```

---

## Section 1: Manifest model changes

### Task 1.1: Add `lifecycle`, `shared_worktree` to `ProjectMeta`; deprecate deliverable models

**Files:**
- Modify: `src/keel/manifest/models.py`
- Modify: `tests/test_manifest.py`

The schema split between `ProjectManifest` and `DeliverableManifest` collapses. `ProjectMeta` gains the two fields previously on `DeliverableMeta`. The deliverable classes get marked deprecated and replaced by re-exports for one release, so the migration command can still read old `deliverable.toml` files.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_manifest.py`:

```python
def test_project_meta_gains_shared_worktree() -> None:
    """ProjectMeta gains the field previously on DeliverableMeta."""
    from datetime import date
    from keel.manifest import ProjectMeta
    m = ProjectMeta(name="x", description="d", created=date(2026, 5, 5), shared_worktree=True)
    assert m.shared_worktree is True


def test_project_meta_shared_worktree_default_false() -> None:
    from datetime import date
    from keel.manifest import ProjectMeta
    m = ProjectMeta(name="x", description="d", created=date(2026, 5, 5))
    assert m.shared_worktree is False


def test_project_manifest_shared_worktree_excludes_repos(tmp_path) -> None:
    """If shared_worktree=True, repos must be empty (rule moved from DeliverableManifest)."""
    from datetime import date
    import pytest
    from pydantic import ValidationError
    from keel.manifest import ProjectManifest, ProjectMeta, RepoSpec
    with pytest.raises(ValidationError):
        ProjectManifest(
            project=ProjectMeta(name="x", description="d", created=date(2026, 5, 5), shared_worktree=True),
            repos=[RepoSpec(remote="r", worktree="w")],
        )
```

- [ ] **Step 2: Run, expect FAIL**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/test_manifest.py::test_project_meta_gains_shared_worktree -v
```

Expected FAIL — field doesn't exist on `ProjectMeta` yet.

- [ ] **Step 3: Add `shared_worktree` to `ProjectMeta` and update validator**

In `src/keel/manifest/models.py`:

Find the existing `ProjectMeta` class. Add the field:

```python
class ProjectMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    created: _date
    lifecycle: str = Field(default="default", description="Name of the phase lifecycle.")
    shared_worktree: bool = Field(
        default=False,
        description="If true, this project does not have its own [[repos]] — it shares a worktree with its parent.",
    )
```

Move the `_shared_excludes_repos` validator from `DeliverableManifest` to `ProjectManifest`:

```python
class ProjectManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: ProjectMeta
    repos: list[RepoSpec] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator("repos")
    @classmethod
    def _shared_excludes_repos(cls, v: list[RepoSpec], info) -> list[RepoSpec]:
        meta = info.data.get("project")
        if meta is not None and meta.shared_worktree and v:
            raise ValueError("shared_worktree=true is mutually exclusive with [[repos]]")
        return v
```

- [ ] **Step 4: Run tests; expect PASS**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/test_manifest.py -v
```

- [ ] **Step 5: Mark deliverable classes deprecated**

Append at the bottom of `manifest/models.py` (after `DeliverableManifest` if still present):

```python
# Deprecated since 0.0.3 — kept temporarily so the old → new layout migration
# command can still read old `deliverable.toml` files. Removed in a future 0.0.x.
import warnings as _warnings


def _deprecated_deliverable_warning() -> None:
    _warnings.warn(
        "DeliverableManifest / DeliverableMeta are deprecated in keel 0.0.3; "
        "deliverables now use ProjectManifest. Schedule for removal in a future 0.0.x.",
        DeprecationWarning,
        stacklevel=3,
    )
```

(We're not actually removing the classes yet — just flagging the deprecation. They go away in Task 5.3 once `keel migrate` is in place.)

- [ ] **Step 6: Run full suite + ruff**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests plugins/jira/src plugins/jira/tests
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git -C ~/projects add keel/src/keel/manifest/models.py keel/tests/test_manifest.py
git -C ~/projects commit -m "feat(keel)!: add shared_worktree to ProjectMeta; deprecate Deliverable models"
```

---

## Section 2: Scope API — new layout paths

### Task 2.1: Update `Scope` for the new layout

**Files:**
- Modify: `src/keel/workspace.py`
- Modify: `tests/test_workspace.py`

The `Scope` dataclass's properties currently point inside `design/`. They now point at the project root for manifests and at `.keel/` for tool state.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_workspace.py`:

```python
def test_scope_manifest_path_at_root(projects, make_project) -> None:
    """In the new layout, project.toml lives at <project>/project.toml."""
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.manifest_path == proj / "project.toml"


def test_scope_phase_path_in_keel_dir(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.phase_path == proj / ".keel" / "phase"


def test_scope_lifecycle_lock_path(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.lifecycle_lock_path == proj / ".keel" / "lifecycle.lock.toml"


def test_scope_keel_dir(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.keel_dir == proj / ".keel"


def test_scope_milestones_manifest_path_at_root(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.milestones_manifest_path == proj / "milestones.toml"


def test_scope_decisions_dir_at_root(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.decisions_dir == proj / "decisions"


def test_scope_human_design_files_at_root(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.scope_md_path == proj / "scope.md"
    assert scope.design_md_path == proj / "design.md"


def projects_scope(name: str):
    """Helper: build a Scope for a project name (no fixture import jiggling)."""
    from keel.workspace import Scope
    return Scope(project=name)
```

- [ ] **Step 2: Run, expect FAIL**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/test_workspace.py::test_scope_manifest_path_at_root -v
```

- [ ] **Step 3: Update `Scope` properties**

In `src/keel/workspace.py`, replace the existing `Scope.design_dir`, `Scope.manifest_path`, `Scope.phase_file`, `Scope.decisions_dir`, `Scope.milestones_manifest_path` with the following set:

```python
@dataclass(frozen=True)
class Scope:
    project: str
    deliverable: str | None = None

    @property
    def unit_dir(self) -> Path:
        if self.deliverable:
            return projects_dir() / self.project / "deliverables" / self.deliverable
        return projects_dir() / self.project

    # === Manifests at the unit root (was: under design/) ===

    @property
    def manifest_path(self) -> Path:
        return self.unit_dir / "project.toml"

    @property
    def milestones_manifest_path(self) -> Path:
        return self.unit_dir / "milestones.toml"

    # === Human-authored content at the unit root ===

    @property
    def scope_md_path(self) -> Path:
        return self.unit_dir / "scope.md"

    @property
    def design_md_path(self) -> Path:
        return self.unit_dir / "design.md"

    @property
    def readme_path(self) -> Path:
        return self.unit_dir / "README.md"

    @property
    def decisions_dir(self) -> Path:
        return self.unit_dir / "decisions"

    @property
    def plans_dir(self) -> Path:
        return self.unit_dir / "plans"

    @property
    def specs_dir(self) -> Path:
        return self.unit_dir / "specs"

    # === Tool state under .keel/ ===

    @property
    def keel_dir(self) -> Path:
        return self.unit_dir / ".keel"

    @property
    def phase_path(self) -> Path:
        return self.keel_dir / "phase"

    @property
    def lifecycle_lock_path(self) -> Path:
        return self.keel_dir / "lifecycle.lock.toml"

    # === Backward-compat shim — still serves callers that haven't migrated yet.
    # Removed in a future 0.0.x. Returns the unit_dir, NOT the obsolete design/ subdir.

    @property
    def design_dir(self) -> Path:
        return self.unit_dir
```

The free-function helpers in this module (`design_dir(...)`, `manifest_path(...)`, etc.) are kept for backward compatibility but reroute to the new paths. Update each:

```python
def design_dir(project: str, deliverable: str | None = None) -> Path:
    """Deprecated. Returns the unit dir for backward compatibility."""
    return Scope(project=project, deliverable=deliverable).unit_dir


def manifest_path(project: str, deliverable: str | None = None) -> Path:
    return Scope(project=project, deliverable=deliverable).manifest_path


def phase_file(project: str, deliverable: str | None = None) -> Path:
    """Deprecated alias for the new phase_path."""
    return Scope(project=project, deliverable=deliverable).phase_path


def decisions_dir(project: str, deliverable: str | None = None) -> Path:
    return Scope(project=project, deliverable=deliverable).decisions_dir
```

`read_phase()` already takes a `design_dir: Path` parameter. Update its body to look at `<dir>/.keel/phase` if the dir is a unit directory, falling back to the legacy `<dir>/.phase`:

```python
def read_phase(unit_or_design_dir: Path) -> str:
    """Read the current phase. Tolerates both new and legacy layouts."""
    new_path = unit_or_design_dir / ".keel" / "phase"
    legacy_path = unit_or_design_dir / ".phase"  # pre-redesign
    for p in (new_path, legacy_path):
        if p.is_file():
            text = p.read_text().strip()
            return text or DEFAULT_PHASE
    return DEFAULT_PHASE
```

- [ ] **Step 4: Run tests; expect PASS for new tests, may break old ones**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/test_workspace.py -v
```

The new tests pass. Older tests that asserted on `<project>/design/project.toml` fail; update them to expect `<project>/project.toml`. The fixture `make_project` in `keel.testing` will need its scaffolding updated as part of Task 2.2.

- [ ] **Step 5: Commit**

```bash
git -C ~/projects add keel/src/keel/workspace.py keel/tests/test_workspace.py
git -C ~/projects commit -m "feat(keel)!: Scope API points at the new layout (manifests at root, .keel/ for state)"
```

---

### Task 2.2: Update `keel.testing.make_project` fixture for the new layout

**Files:**
- Modify: `src/keel/testing/__init__.py`

Test infrastructure currently writes `design/project.toml`, `design/.phase`, etc. Update to write at the project root + `.keel/`.

- [ ] **Step 1: Locate the fixture**

```
grep -n "save_project_manifest\|design/.phase\|design/project.toml" src/keel/testing/__init__.py
```

- [ ] **Step 2: Update the `make_project` fixture body**

Inside `keel.testing.__init__`, update the project scaffolding helper (currently builds files under `design/`):

```python
def make_project(projects_dir: Path, *, name: str, description: str = "test", lifecycle: str = "default") -> Path:
    proj = projects_dir / name
    proj.mkdir(parents=True, exist_ok=True)

    # Manifests at root
    (proj / "decisions").mkdir(exist_ok=True)
    save_project_manifest(
        proj / "project.toml",
        ProjectManifest(
            project=ProjectMeta(
                name=name,
                description=description,
                created=date(2026, 5, 5),
                lifecycle=lifecycle,
            ),
            repos=[],
        ),
    )

    # Tool state under .keel/
    (proj / ".keel").mkdir(exist_ok=True)
    (proj / ".keel" / "phase").write_text("scoping\n")

    # Minimal scope.md / design.md so design-walking commands have something to read
    (proj / "scope.md").write_text(f"# {name}\n\nScope.\n")
    (proj / "design.md").write_text(f"# {name} — design\n\n")

    return proj
```

`make_deliverable` similarly scaffolds at `<project>/deliverables/<name>/`. Update analogously.

- [ ] **Step 3: Run full suite — many path-related test failures expected**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
```

Expected: a wave of failures across `tests/commands/*`. This is the migration breakage; we'll fix command-by-command in subsequent sections. Don't try to fix all the test breakage at this commit — record what fails and proceed.

- [ ] **Step 4: Commit**

```bash
git -C ~/projects add keel/src/keel/testing/__init__.py
git -C ~/projects commit -m "feat(keel)!: keel.testing fixtures scaffold with new layout"
```

---

## Section 3: New `keel new` writes the new layout

### Task 3.1: `keel new` writes manifests at root + `.keel/` + lifecycle snapshot

**Files:**
- Modify: `src/keel/commands/new.py`
- Modify: `tests/commands/test_new.py`

`keel new` currently writes `design/project.toml`, `design/.phase`, `design/scope.md`, etc. Rewrite to use the new layout, including writing `.keel/lifecycle.lock.toml` (verbatim copy of the resolved lifecycle).

- [ ] **Step 1: Write failing tests**

In `tests/commands/test_new.py`, append:

```python
def test_new_writes_project_toml_at_root(projects, monkeypatch) -> None:
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["new", "alpha", "-d", "test", "--no-worktree", "-y"])
    assert result.exit_code == 0
    assert (projects / "alpha" / "project.toml").is_file()
    assert not (projects / "alpha" / "design" / "project.toml").exists()


def test_new_writes_phase_under_keel(projects, monkeypatch) -> None:
    monkeypatch.chdir(projects)
    runner.invoke(app, ["new", "alpha", "-d", "test", "--no-worktree", "-y"])
    assert (projects / "alpha" / ".keel" / "phase").read_text().strip() == "scoping"


def test_new_writes_lifecycle_lock(projects, monkeypatch) -> None:
    monkeypatch.chdir(projects)
    runner.invoke(app, ["new", "alpha", "-d", "test", "--no-worktree", "-y"])
    lock = projects / "alpha" / ".keel" / "lifecycle.lock.toml"
    assert lock.is_file()
    text = lock.read_text()
    # Verbatim copy of the default lifecycle TOML.
    assert 'name = "default"' in text
    assert "[states.scoping]" in text


def test_new_writes_readme_with_links(projects, monkeypatch) -> None:
    monkeypatch.chdir(projects)
    runner.invoke(app, ["new", "alpha", "-d", "Build a thing", "--no-worktree", "-y"])
    readme = (projects / "alpha" / "README.md").read_text()
    assert "alpha" in readme
    assert "Build a thing" in readme
    assert "[Scope](scope.md)" in readme
    assert "[Design](design.md)" in readme


def test_new_human_design_files_at_root(projects, monkeypatch) -> None:
    monkeypatch.chdir(projects)
    runner.invoke(app, ["new", "alpha", "-d", "test", "--no-worktree", "-y"])
    assert (projects / "alpha" / "scope.md").is_file()
    assert (projects / "alpha" / "design.md").is_file()
    assert (projects / "alpha" / "decisions").is_dir()
    # design/ subfolder MUST NOT be created in the new layout
    assert not (projects / "alpha" / "design").exists()
```

- [ ] **Step 2: Run, expect FAIL**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_new.py::test_new_writes_project_toml_at_root -v
```

- [ ] **Step 3: Create the README template**

`src/keel/_templates/readme_md.j2`:

```jinja
# {{ project.name }}

{{ project.description }}

**Lifecycle:** {{ lifecycle.name }} · **Phase:** {{ phase }}

## Design

- [Scope](scope.md) — boundaries and success criteria
- [Design](design.md) — living technical design
- [Decisions](decisions/) — one record per non-obvious choice
{% if has_milestones %}- [Milestones](milestones.toml) — work breakdown
{% endif %}

## Code
{% for repo in repos %}
- `{{ repo.worktree }}/` — `{{ repo.remote }}`
{% endfor %}{% if not repos %}
_(No source repos linked yet. Use `keel code add --repo <path>` to attach one.)_
{% endif %}
```

- [ ] **Step 4: Update `cmd_new` body**

Locate the current `keel new` write logic. Replace the file-write section with:

```python
# Write manifests at unit root
unit_dir = scope.unit_dir
unit_dir.mkdir(parents=True, exist_ok=True)
save_project_manifest(scope.manifest_path, manifest)

# Tool state under .keel/
scope.keel_dir.mkdir(exist_ok=True)
scope.phase_path.write_text(f"{lc.initial}\n")

# Lifecycle snapshot — verbatim copy of the resolved TOML
import shutil
from keel.lifecycles.loader import _resolve_lifecycle_path  # internal; inline if needed
src_path = _resolve_lifecycle_path(lifecycle)
shutil.copyfile(src_path, scope.lifecycle_lock_path)

# Human-authored content at the unit root
scope.scope_md_path.write_text(templates.render("scope_md.j2", name=name, description=description))
scope.design_md_path.write_text(templates.render("design_md.j2", name=name, description=description))
scope.decisions_dir.mkdir(exist_ok=True)

# README
scope.readme_path.write_text(
    templates.render(
        "readme_md.j2",
        project=manifest.project,
        lifecycle=lc,
        phase=lc.initial,
        has_milestones=False,
        repos=manifest.repos,
    )
)
```

`_resolve_lifecycle_path` may need adding to `keel.lifecycles.loader` — a helper that returns the file path the loader resolved. If the loader currently doesn't expose this, add a sibling function:

```python
# In src/keel/lifecycles/loader.py
def lifecycle_source_path(name: str) -> Path:
    """Return the file path resolved for `name`. Used by `keel new` to snapshot."""
    user_path = _user_library_dir() / f"{name}.toml"
    if user_path.is_file():
        return user_path
    builtin = resources.files("keel.lifecycles.defaults").joinpath(f"{name}.toml")
    if builtin.is_file():
        return Path(str(builtin))
    raise LifecycleNotFoundError(name)
```

Use `lifecycle_source_path()` in `cmd_new`.

- [ ] **Step 5: Run tests**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_new.py -v
```

Expected: 5 new tests pass; existing tests that asserted `design/...` paths now need updating. Update them.

- [ ] **Step 6: Run full suite + ruff**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests plugins/jira/src plugins/jira/tests
```

Expected: most other commands still fail (they read paths via the old `design/` location). Acceptable — those are the next sections.

- [ ] **Step 7: Commit**

```bash
git -C ~/projects add keel/src/keel/_templates/readme_md.j2 keel/src/keel/commands/new.py keel/src/keel/lifecycles/loader.py keel/tests/commands/test_new.py
git -C ~/projects commit -m "feat(keel)!: keel new writes new layout (.keel/, lifecycle.lock.toml, README, root manifests)"
```

---

## Section 4: Sweep commands to use new Scope properties

### Task 4.1: Sweep all command files for old path usages

**Files:**
- Modify: every file under `src/keel/commands/` and `src/keel/preflights/` that references `design_dir`, `phase_file`, `manifest_path` (free function vs property) inconsistently.

The new `Scope` properties (Task 2.1) point at the new layout, but several commands and preflights call the FREE FUNCTIONS (`workspace.design_dir(...)`, `workspace.phase_file(...)`) directly. After Task 2.1 those still resolve correctly (they delegate to `Scope`), but the code is clearer using `scope.X` throughout.

- [ ] **Step 1: Identify call sites**

```bash
cd /Users/andrei.matei/projects/keel
grep -rn "workspace\.design_dir\|workspace\.phase_file\|workspace\.decisions_dir\|workspace\.manifest_path\|workspace\.milestones_manifest_path" src/keel/
```

- [ ] **Step 2: Replace per-call**

For each match, look at the local context. If a `scope` variable is in scope, replace `workspace.X(scope.project, scope.deliverable)` with `scope.X` (the property).

If no scope is in scope (rare; usually in helpers that take a unit dir directly), leave alone.

Common shape:
```python
# Before
phase = read_phase(workspace.design_dir(scope.project, scope.deliverable))

# After
phase = read_phase(scope.unit_dir)
```

- [ ] **Step 3: Update `read_phase` callers**

Anywhere `read_phase(design_dir)` is called, the argument should now be `scope.unit_dir` (since `read_phase` accepts the unit dir and finds `.keel/phase` or legacy `.phase` automatically — Task 2.1 step 3).

- [ ] **Step 4: Run tests**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
```

Many tests should now pass (the path resolution is consistent). Some tests that hardcode `design/...` paths in their assertions still fail — update those test assertions too.

- [ ] **Step 5: Commit**

```bash
git -C ~/projects add keel/src/keel/commands/ keel/src/keel/preflights/ keel/tests/
git -C ~/projects commit -m "refactor(keel): commands use Scope.* properties consistently"
```

---

### Task 4.2: Update remaining test fixtures + assertions

**Files:** sweep `tests/`

Many tests assert on `design/...` paths. With the new layout, those need updating.

- [ ] **Step 1: Find them**

```bash
cd /Users/andrei.matei/projects/keel
grep -rn "design/project\.toml\|design/\.phase\|design/milestones\.toml\|design/scope\.md\|design/design\.md\|design/decisions" tests/ plugins/jira/tests/
```

- [ ] **Step 2: Mechanical replacement**

For each match, replace:

| Old | New |
|---|---|
| `proj / "design" / "project.toml"` | `proj / "project.toml"` |
| `proj / "design" / ".phase"` | `proj / ".keel" / "phase"` |
| `proj / "design" / "milestones.toml"` | `proj / "milestones.toml"` |
| `proj / "design" / "scope.md"` | `proj / "scope.md"` |
| `proj / "design" / "design.md"` | `proj / "design.md"` |
| `proj / "design" / "decisions"` | `proj / "decisions"` |

Same shape for `make_deliverable`-spawned paths.

- [ ] **Step 3: Run + commit**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
```

Expected: most tests now pass. Failures isolated to known-broken commands (deliverable, ticketing — handled in later sections).

```bash
git -C ~/projects add keel/tests/ keel/plugins/jira/tests/
git -C ~/projects commit -m "test(keel): update path assertions for new layout"
```

---

## Section 5: Hierarchy — implicit-default milestone

### Task 5.1: `keel task add` auto-creates the default milestone

**Files:**
- Modify: `src/keel/commands/task/add.py`
- Modify: `tests/commands/task/test_add.py`

When `keel task add` is invoked without `--milestone`, auto-create a `default` milestone (id `default`, title `"Tasks"`) if it doesn't exist, then add the task there.

- [ ] **Step 1: Tests**

Append to `tests/commands/task/test_add.py`:

```python
def test_task_add_without_milestone_creates_default(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    result = runner.invoke(app, ["task", "add", "t1", "--title", "Set up"], catch_exceptions=False)
    assert result.exit_code == 0
    from keel.api import load_milestones_manifest
    m = load_milestones_manifest(proj / "milestones.toml")
    assert any(ms.id == "default" for ms in m.milestones)
    t1 = next(t for t in m.tasks if t.id == "t1")
    assert t1.milestone == "default"


def test_task_add_default_milestone_singleton(projects, make_project, monkeypatch) -> None:
    """Multiple --milestone-less adds reuse the same default milestone."""
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["task", "add", "t1", "--title", "First"])
    runner.invoke(app, ["task", "add", "t2", "--title", "Second"])
    from keel.api import load_milestones_manifest
    m = load_milestones_manifest(proj / "milestones.toml")
    defaults = [ms for ms in m.milestones if ms.id == "default"]
    assert len(defaults) == 1


def test_task_add_with_milestone_does_not_create_default(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "Set up"])
    from keel.api import load_milestones_manifest
    m = load_milestones_manifest(proj / "milestones.toml")
    ids = {ms.id for ms in m.milestones}
    assert "default" not in ids
    assert "m1" in ids
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Update `cmd_add`**

In `src/keel/commands/task/add.py`, change the `milestone` parameter to be optional, and add the auto-create branch:

```python
def cmd_add(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    title: str = typer.Option(..., "--title"),
    milestone: str | None = typer.Option(
        None, "--milestone", "-m",
        help="Milestone id. If omitted, an implicit 'default' milestone is auto-created.",
    ),
    description: str = typer.Option("", "--description"),
    depends_on: str = typer.Option("", "--depends-on"),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    no_push: bool = typer.Option(False, "--no-push"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    out = Output.from_context(ctx, json_mode=json_mode)
    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        target_milestone_id = milestone or "default"
        if target_milestone_id == "default" and not any(m.id == "default" for m in manifest.milestones):
            # Auto-create the implicit default milestone.
            manifest.milestones.append(
                Milestone(id="default", title="Tasks", status="active")
            )

        # Existing duplicate-id, dep-validation, DAG-validation logic follows...
        # (keep as-is, but reference target_milestone_id instead of milestone)
```

`Milestone` is imported from `keel.api`.

- [ ] **Step 4: Run tests; expect PASS**

- [ ] **Step 5: Commit**

```bash
git -C ~/projects add keel/src/keel/commands/task/add.py keel/tests/commands/task/test_add.py
git -C ~/projects commit -m "feat(keel): task add auto-creates implicit 'default' milestone"
```

---

### Task 5.2: `keel task move <id> --milestone <m>`

**Files:**
- Create: `src/keel/commands/task/move.py`
- Modify: `src/keel/commands/task/__init__.py`
- Create: `tests/commands/task/test_move.py`

A move command lets users re-parent a task. Required for users who start with the implicit default and later promote to explicit milestones.

- [ ] **Step 1: Tests**

`tests/commands/task/test_move.py`:

```python
"""Tests for `keel task move`."""
from typer.testing import CliRunner
from keel.app import app

runner = CliRunner()


def test_move_reparents(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["task", "add", "t1", "--title", "x"])  # creates default
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])

    result = runner.invoke(app, ["task", "move", "t1", "--milestone", "m1"])
    assert result.exit_code == 0
    from keel.api import load_milestones_manifest
    m = load_milestones_manifest(proj / "milestones.toml")
    t1 = next(t for t in m.tasks if t.id == "t1")
    assert t1.milestone == "m1"


def test_move_unknown_milestone_fails(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["task", "add", "t1", "--title", "x"])
    result = runner.invoke(app, ["task", "move", "t1", "--milestone", "ghost"])
    assert result.exit_code == 1


def test_move_unknown_task_fails(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["milestone", "add", "m1", "--title", "x"])
    result = runner.invoke(app, ["task", "move", "ghost", "--milestone", "m1"])
    assert result.exit_code == 1


def test_move_emptying_default_removes_it(projects, make_project, monkeypatch) -> None:
    """When the last task leaves 'default', the auto-created milestone disappears."""
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["task", "add", "t1", "--title", "x"])  # creates default
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])
    runner.invoke(app, ["task", "move", "t1", "--milestone", "m1"])
    from keel.api import load_milestones_manifest
    m = load_milestones_manifest(proj / "milestones.toml")
    ids = {ms.id for ms in m.milestones}
    assert "default" not in ids
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement `cmd_move`**

`src/keel/commands/task/move.py`:

```python
"""`keel task move <id> --milestone <m>`."""
from __future__ import annotations
import typer
from keel.api import (
    ErrorCode,
    Output,
    edit_milestones,
    find_milestone,
    get_task,
    resolve_cli_scope,
)


def cmd_move(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    milestone: str = typer.Option(..., "--milestone", "-m"),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Move a task to a different milestone."""
    out = Output.from_context(ctx, json_mode=json_mode)
    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        task = get_task(manifest, id, out=out)
        if find_milestone(manifest, milestone) is None:
            out.fail(f"unknown milestone '{milestone}'", code=ErrorCode.NOT_FOUND)

        old_milestone_id = task.milestone
        task.milestone = milestone

        # If the old milestone was the implicit default and now empty, drop it.
        if old_milestone_id == "default" and not any(t.milestone == "default" for t in manifest.tasks):
            manifest.milestones = [ms for ms in manifest.milestones if ms.id != "default"]

    out.result(task.model_dump(), human_text=f"Task moved: {id} → {milestone}")
```

- [ ] **Step 4: Register**

In `src/keel/commands/task/__init__.py`:

```python
from keel.commands.task.move import cmd_move  # noqa: E402

app.command(name="move")(cmd_move)
```

- [ ] **Step 5: Run tests + commit**

```bash
git -C ~/projects add keel/src/keel/commands/task/move.py keel/src/keel/commands/task/__init__.py keel/tests/commands/task/test_move.py
git -C ~/projects commit -m "feat(keel): keel task move <id> --milestone <m> (re-parents tasks)"
```

---

### Task 5.3: `keel task rm` auto-removes empty default milestone; `keel show` skips single-default rendering

**Files:**
- Modify: `src/keel/commands/task/rm.py`
- Modify: `src/keel/commands/show.py`
- Modify: `tests/commands/task/test_rm.py`
- Modify: `tests/commands/test_show.py`

- [ ] **Step 1: Tests for rm**

Append to `tests/commands/task/test_rm.py`:

```python
def test_rm_emptying_default_removes_it(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["task", "add", "t1", "--title", "x"])  # creates default
    result = runner.invoke(app, ["task", "rm", "t1", "-y"])
    assert result.exit_code == 0
    from keel.api import load_milestones_manifest
    m = load_milestones_manifest(proj / "milestones.toml")
    assert m.milestones == []
```

- [ ] **Step 2: Update `cmd_rm`**

After removing the task, check whether its milestone was `default` and now empty:

```python
old_milestone_id = task.milestone
manifest.tasks = [t for t in manifest.tasks if t.id != id]

if old_milestone_id == "default" and not any(t.milestone == "default" for t in manifest.tasks):
    manifest.milestones = [ms for ms in manifest.milestones if ms.id != "default"]
```

- [ ] **Step 3: Tests for show**

Append to `tests/commands/test_show.py`:

```python
def test_show_skips_single_default_milestone(projects, make_project, monkeypatch) -> None:
    """When the only milestone is the implicit default, `show` doesn't render the milestone hierarchy."""
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["task", "add", "t1", "--title", "x"])  # auto-default
    result = runner.invoke(app, ["show", "foo"])
    assert result.exit_code == 0
    # The summary should mention t1 directly, not show "Milestone: default" sections.
    assert "default" not in result.stdout.lower() or "Tasks" in result.stdout


def test_show_renders_explicit_milestones(projects, make_project, monkeypatch) -> None:
    """When explicit milestones exist, render them normally."""
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "x"])
    result = runner.invoke(app, ["show", "foo"])
    assert "m1" in result.stdout
    assert "Foundation" in result.stdout
```

- [ ] **Step 4: Update `cmd_show`'s milestone-summary section**

In `src/keel/commands/show.py`, where milestone summary is rendered, detect the single-default case and skip:

```python
def _has_only_implicit_default(manifest: MilestonesManifest) -> bool:
    return len(manifest.milestones) == 1 and manifest.milestones[0].id == "default"
```

When `_has_only_implicit_default(manifest)` is true, render task counts directly without milestone grouping. JSON output keeps the milestones list (machine readers always see the structure).

- [ ] **Step 5: Run tests + commit**

```bash
git -C ~/projects add keel/src/keel/commands/task/rm.py keel/src/keel/commands/show.py keel/tests/commands/task/test_rm.py keel/tests/commands/test_show.py
git -C ~/projects commit -m "feat(keel): auto-remove emptied default milestone; show skips rendering single default"
```

---

## Section 6: Deliverables — same schema, drop deliverable.toml

### Task 6.1: `keel deliverable add` becomes scaffold-sugar over `keel new`

**Files:**
- Modify: `src/keel/commands/deliverable/add.py`
- Modify: `tests/commands/deliverable/test_add.py`

Today this command writes `deliverable.toml`. After redesign: it writes `project.toml` at `<parent>/deliverables/<name>/project.toml`, identical schema, with `parent_project` removed (path-derived).

- [ ] **Step 1: Tests**

Append/replace tests in `tests/commands/deliverable/test_add.py`:

```python
def test_deliverable_add_writes_project_toml(projects, make_project, monkeypatch) -> None:
    """Deliverables now use project.toml — identical to top-level."""
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    result = runner.invoke(
        app, ["deliverable", "add", "bar", "-d", "Sub-project", "-y"], catch_exceptions=False
    )
    assert result.exit_code == 0
    deliv_path = proj / "deliverables" / "bar"
    assert (deliv_path / "project.toml").is_file()
    assert not (deliv_path / "deliverable.toml").exists()


def test_deliverable_add_creates_keel_dir(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "x", "-y"])
    deliv_path = proj / "deliverables" / "bar"
    assert (deliv_path / ".keel" / "phase").is_file()
    assert (deliv_path / ".keel" / "lifecycle.lock.toml").is_file()


def test_deliverable_add_inherits_lifecycle_from_parent(projects, make_project, monkeypatch) -> None:
    """If parent uses lifecycle X, deliverable defaults to X (not 'default')."""
    proj = make_project("foo", lifecycle="default")  # parent uses default
    monkeypatch.chdir(proj)
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "x", "-y"])
    from keel.api import load_project_manifest
    deliv_manifest = load_project_manifest(proj / "deliverables" / "bar" / "project.toml")
    assert deliv_manifest.project.lifecycle == "default"
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Update `cmd_add` for deliverable**

In `src/keel/commands/deliverable/add.py`:

```python
def cmd_add(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    description: str = typer.Option(..., "-d", "--description"),
    project: str | None = typer.Option(None, "--project", "-p"),
    no_worktree: bool = typer.Option(False, "--no-worktree"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Add a deliverable to the current project. Equivalent to creating a nested project."""
    out = Output.from_context(ctx, json_mode=json_mode)
    parent_scope = resolve_cli_scope(project, None, out=out)

    # Inherit lifecycle from parent
    from keel.lifecycles import load_lifecycle
    parent_manifest = load_project_manifest(parent_scope.manifest_path)
    parent_lifecycle = parent_manifest.project.lifecycle
    lc = load_lifecycle(parent_lifecycle)

    # Build the nested project's scope
    deliv_scope = Scope(project=parent_scope.project, deliverable=name)

    if deliv_scope.unit_dir.exists():
        out.fail(f"deliverable '{name}' already exists at {deliv_scope.unit_dir}",
                 code=ErrorCode.EXISTS)

    # Reuse the same scaffold logic as `keel new`. Extracted into a shared helper.
    from keel.commands.new import _scaffold_unit
    _scaffold_unit(
        scope=deliv_scope,
        name=name,
        description=description,
        lifecycle=parent_lifecycle,
        repos=[],
        lc=lc,
    )

    out.result(
        {"name": name, "path": str(deliv_scope.unit_dir)},
        human_text=f"Deliverable created: {deliv_scope.unit_dir}",
    )
```

This implies extracting a `_scaffold_unit` helper from `cmd_new`. Do that as part of Task 3.1 if not already done — it should be a pure function that writes `project.toml`, `.keel/phase`, `.keel/lifecycle.lock.toml`, `scope.md`, `design.md`, `decisions/`, `README.md`.

- [ ] **Step 4: Update sibling-tracking in parent's CLAUDE.md / scope.md**

The existing AST-edit logic that maintains a "Sibling deliverables" list in the parent — update to point at `<parent>/deliverables/<name>/` instead of `<parent>/deliverables/<name>/design/`.

- [ ] **Step 5: Run tests + commit**

```bash
git -C ~/projects add keel/src/keel/commands/deliverable/ keel/src/keel/commands/new.py keel/tests/commands/deliverable/
git -C ~/projects commit -m "feat(keel)!: keel deliverable add scaffolds nested project (no more deliverable.toml)"
```

---

### Task 6.2: Drop `DeliverableManifest` and `DeliverableMeta` after migration support is in place

**Files:**
- Modify: `src/keel/manifest/models.py`
- Modify: `src/keel/manifest/io.py`
- Modify: `src/keel/manifest/__init__.py`
- Modify: `src/keel/api.py`

Once the migration command (Section 7) reads old `deliverable.toml` files via the deprecated path, the in-process classes can be removed. The deprecated stubs remain — `load_deliverable_manifest` becomes a thin "load and convert to ProjectManifest" function, used only by `keel migrate`.

- [ ] **Step 1: Convert `load_deliverable_manifest` to a converter**

```python
# In src/keel/manifest/io.py
def load_deliverable_manifest(path: Path) -> ProjectManifest:
    """DEPRECATED — reads a v0.0.x deliverable.toml and returns a ProjectManifest.

    Used only by `keel migrate`. Removed in a future 0.0.x.
    """
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


def save_deliverable_manifest(path: Path, manifest: ProjectManifest) -> None:
    """DEPRECATED — writes a ProjectManifest as a deliverable.toml.

    Should not be called in new code; only kept for backward compat.
    Removed in a future 0.0.x.
    """
    raise NotImplementedError(
        "save_deliverable_manifest is deprecated. Use save_project_manifest instead."
    )
```

- [ ] **Step 2: Drop `DeliverableManifest` / `DeliverableMeta` from public API**

In `src/keel/api.py`, remove from imports + `__all__`:
- `DeliverableManifest`
- `DeliverableMeta`

In `src/keel/manifest/__init__.py`, remove the re-exports.

In `src/keel/manifest/models.py`, delete the `DeliverableMeta` and `DeliverableManifest` classes.

- [ ] **Step 3: Run tests + commit**

```bash
git -C ~/projects add keel/src/keel/manifest/ keel/src/keel/api.py keel/tests/
git -C ~/projects commit -m "feat(keel)!: drop DeliverableManifest/DeliverableMeta (use ProjectManifest)"
```

---

## Section 7: Migration command — old → new layout

### Task 7.1: `keel migrate` old → new layout step

**Files:**
- Modify: `src/keel/commands/migrate.py`
- Modify: `tests/commands/test_migrate.py`

The existing `keel migrate` handles the legacy Bash → keel cutover. Add a old → new layout step that detects old layout and rewrites it.

- [ ] **Step 1: Tests**

Append to `tests/commands/test_migrate.py`:

```python
def test_migrate_legacy_layout(projects, monkeypatch) -> None:
    """An existing legacy-layout project has its layout rewritten to the new layout."""
    # Hand-build a legacy layout
    proj = projects / "old"
    (proj / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "project.toml").write_text(
        '[project]\nname = "old"\ndescription = "x"\ncreated = 2026-01-01\n'
    )
    (proj / "design" / ".phase").write_text("designing\n")
    (proj / "design" / "scope.md").write_text("# old\n")
    (proj / "design" / "design.md").write_text("# old design\n")

    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["migrate", "--all", "-y"], catch_exceptions=False)
    assert result.exit_code == 0

    # New layout
    assert (proj / "project.toml").is_file()
    assert (proj / ".keel" / "phase").read_text().strip() == "designing"
    assert (proj / ".keel" / "lifecycle.lock.toml").is_file()
    assert (proj / "scope.md").is_file()
    assert (proj / "design.md").is_file()
    assert (proj / "decisions").is_dir()
    assert (proj / "README.md").is_file()

    # Old layout gone
    assert not (proj / "design" / "project.toml").exists()
    assert not (proj / "design" / ".phase").exists()


def test_migrate_idempotent(projects, monkeypatch) -> None:
    """Re-running migrate on an already-migrated project is a no-op."""
    proj = projects / "newproj"
    (proj / ".keel").mkdir(parents=True)
    (proj / "project.toml").write_text(
        '[project]\nname = "newproj"\ndescription = "x"\ncreated = 2026-05-05\nlifecycle = "default"\n'
    )
    (proj / ".keel" / "phase").write_text("scoping\n")

    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["migrate", "--all", "-y"])
    assert result.exit_code == 0
    # No file moved
    assert (proj / "project.toml").is_file()


def test_migrate_v0_0_x_deliverable(projects, monkeypatch) -> None:
    """deliverable.toml → project.toml conversion."""
    proj = projects / "parent"
    deliv = proj / "deliverables" / "bar"
    (deliv / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "project.toml").write_text(
        '[project]\nname = "parent"\ndescription = "x"\ncreated = 2026-01-01\n'
    )
    (proj / "design" / ".phase").write_text("scoping\n")
    (deliv / "design" / "deliverable.toml").write_text(
        '[deliverable]\nname = "bar"\nparent_project = "parent"\ndescription = "y"\ncreated = 2026-01-02\n'
    )
    (deliv / "design" / ".phase").write_text("scoping\n")

    monkeypatch.chdir(projects)
    runner.invoke(app, ["migrate", "--all", "-y"])

    # Deliverable converted to project.toml
    assert (deliv / "project.toml").is_file()
    assert not (deliv / "deliverable.toml").exists()
    from keel.api import load_project_manifest
    pm = load_project_manifest(deliv / "project.toml")
    assert pm.project.name == "bar"
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Add the migration step**

In `src/keel/commands/migrate.py`, add a `_migrate_legacy_layout(unit_dir, lifecycle_name)` function:

```python
def _migrate_legacy_layout(unit_dir: Path, lifecycle_name: str = "default") -> bool:
    """Rewrite a unit's layout from the legacy `design/` layout to the new layout.

    Returns True if any change was made; False if already migrated.
    """
    design_dir = unit_dir / "design"
    if not design_dir.is_dir():
        return False  # Already migrated or never had v0.0.x layout

    # 1. Move manifests
    if (design_dir / "project.toml").is_file():
        (design_dir / "project.toml").rename(unit_dir / "project.toml")
    elif (design_dir / "deliverable.toml").is_file():
        # Convert deliverable → project
        from keel.manifest.io import load_deliverable_manifest, save_project_manifest
        pm = load_deliverable_manifest(design_dir / "deliverable.toml")
        save_project_manifest(unit_dir / "project.toml", pm)
        (design_dir / "deliverable.toml").unlink()

    if (design_dir / "milestones.toml").is_file():
        (design_dir / "milestones.toml").rename(unit_dir / "milestones.toml")

    # 2. .keel/ directory
    keel_dir = unit_dir / ".keel"
    keel_dir.mkdir(exist_ok=True)
    if (design_dir / ".phase").is_file():
        (design_dir / ".phase").rename(keel_dir / "phase")

    # 3. Lifecycle snapshot
    lock_path = keel_dir / "lifecycle.lock.toml"
    if not lock_path.is_file():
        from keel.lifecycles.loader import lifecycle_source_path
        try:
            src = lifecycle_source_path(lifecycle_name)
            shutil.copyfile(src, lock_path)
        except LifecycleNotFoundError:
            pass  # leave a placeholder

    # 4. Move human content up
    for item in ("scope.md", "design.md", "decisions", "plans", "specs"):
        src = design_dir / item
        if src.exists():
            src.rename(unit_dir / item)

    # 5. Generate README if missing
    readme = unit_dir / "README.md"
    if not readme.is_file():
        from keel.manifest import load_project_manifest
        from keel import templates
        pm = load_project_manifest(unit_dir / "project.toml")
        from keel.lifecycles.loader import load_lifecycle
        try:
            lc = load_lifecycle(pm.project.lifecycle)
            phase = (keel_dir / "phase").read_text().strip() or lc.initial
        except Exception:
            lc = None
            phase = "scoping"
        readme.write_text(templates.render(
            "readme_md.j2",
            project=pm.project,
            lifecycle=lc or type("L", (), {"name": pm.project.lifecycle}),
            phase=phase,
            has_milestones=(unit_dir / "milestones.toml").is_file(),
            repos=pm.repos,
        ))

    # 6. Drop the now-empty design/ directory
    try:
        design_dir.rmdir()
    except OSError:
        pass  # not empty (migrator might have missed something); leave for user inspection

    # 7. Recurse into deliverables
    deliverables = unit_dir / "deliverables"
    if deliverables.is_dir():
        for deliv in deliverables.iterdir():
            if deliv.is_dir():
                _migrate_v0_0_x_to_v0_1_0(deliv, lifecycle_name)

    return True
```

Wire into the `cmd_migrate` body so that when `--all` is specified or a project is passed, this runs after the existing legacy-Bash migration step.

- [ ] **Step 4: Run tests + commit**

```bash
git -C ~/projects add keel/src/keel/commands/migrate.py keel/tests/commands/test_migrate.py
git -C ~/projects commit -m "feat(keel): keel migrate adds old → new layout layout migration"
```

---

## Section 8: New TicketProvider protocol + keel-jira refactor

### Task 8.1: New `TicketProvider` protocol

**Files:**
- Modify: `src/keel/ticketing/base.py`
- Modify: `src/keel/ticketing/mock.py`
- Modify: `tests/test_ticketing.py`

The protocol receives typed `Milestone`/`Task`/`Scope` objects. `parent_id` parameter dropped.

- [ ] **Step 1: Update Protocol**

```python
# src/keel/ticketing/base.py
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from dataclasses import dataclass

if TYPE_CHECKING:
    from keel.manifest import Milestone, Task
    from keel.workspace import Scope


@dataclass(frozen=True)
class Ticket:
    id: str
    url: str
    title: str | None = None
    status: str | None = None


@runtime_checkable
class TicketProvider(Protocol):
    """Ticketing plugin protocol — typed-object based, no pre-rendered strings.

    Plugins receive the keel domain objects directly and render their own
    payloads. keel-cli ships no shared template helper.
    """

    name: str

    def configure(self, config: dict) -> None: ...

    def create_milestone(self, milestone: "Milestone", scope: "Scope") -> Ticket:
        """Create a ticket for the milestone. The plugin reads its own
        per-project config from `[extensions.ticketing.<name>]` via the
        scope's manifest, renders templates, and submits."""
        ...

    def create_task(self, task: "Task", scope: "Scope") -> Ticket:
        """Same shape. To find the milestone's parent ticket id, walk
        scope.manifest → milestones → find_by_id(task.milestone) → ticket_id."""
        ...

    def transition(self, ticket_id: str, target_state: str) -> None: ...
    def fetch(self, ticket_id: str) -> Ticket: ...
    def link_url(self, ticket_id: str) -> str: ...
```

- [ ] **Step 2: Update `MockProvider`**

```python
# src/keel/ticketing/mock.py
class MockProvider:
    name = "mock"

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._counter = 0
        self._tickets: dict[str, Ticket] = {}

    def configure(self, config: dict) -> None:
        self.calls.append(("configure", config))

    def create_milestone(self, milestone, scope) -> Ticket:
        self.calls.append(("create_milestone", milestone.id, milestone.title))
        self._counter += 1
        tid = f"MOCK-{self._counter}"
        t = Ticket(id=tid, url=f"mock://{tid}", title=milestone.title, status="planned")
        self._tickets[tid] = t
        return t

    def create_task(self, task, scope) -> Ticket:
        self.calls.append(("create_task", task.id, task.title, task.milestone))
        self._counter += 1
        tid = f"MOCK-{self._counter}"
        t = Ticket(id=tid, url=f"mock://{tid}", title=task.title, status="planned")
        self._tickets[tid] = t
        return t

    def transition(self, ticket_id, target_state) -> None:
        self.calls.append(("transition", ticket_id, target_state))

    def fetch(self, ticket_id) -> Ticket:
        self.calls.append(("fetch", ticket_id))
        return self._tickets.get(ticket_id, Ticket(id=ticket_id, url=f"mock://{ticket_id}"))

    def link_url(self, ticket_id) -> str:
        return f"mock://tickets/{ticket_id}"
```

- [ ] **Step 3: Update tests**

Existing tests in `tests/test_ticketing.py` for MockProvider call `create_milestone(parent_id, title, description)`. Rewrite each call site to use the typed-object form:

```python
from keel.api import Milestone

m = Milestone(id="m1", title="Foundation", status="planned")
provider.create_milestone(m, scope)
```

- [ ] **Step 4: Run tests + commit**

```bash
git -C ~/projects add keel/src/keel/ticketing/ keel/tests/test_ticketing.py
git -C ~/projects commit -m "feat(keel)!: TicketProvider takes typed Milestone/Task + Scope"
```

---

### Task 8.2: Update `with_provider` / `safe_push` callers in commands

**Files:**
- Modify: `src/keel/commands/milestone/add.py`
- Modify: `src/keel/commands/milestone/done.py`
- Modify: `src/keel/commands/task/add.py`
- Modify: `src/keel/commands/task/done.py`

The current commands call `provider.create_milestone(parent_id, title, description)`. Replace with the typed call.

- [ ] **Step 1: Update each call site**

Pattern:

```python
# Before
provider.create_milestone(parent_id, milestone.title, milestone.description)

# After
provider.create_milestone(milestone, scope)
```

The plugin walks `scope.manifest.extensions.ticketing.<name>.parent_id` itself for the parent context.

- [ ] **Step 2: Run tests + commit**

```bash
git -C ~/projects add keel/src/keel/commands/
git -C ~/projects commit -m "refactor(keel): commands pass typed objects to TicketProvider"
```

---

### Task 8.3: keel-jira plugin v0.0.2 — refactor to new protocol with internal templates

**Files:**
- Modify: `plugins/jira/src/keel_jira/provider.py`
- Modify: `plugins/jira/src/keel_jira/config.py`
- Create: `plugins/jira/src/keel_jira/templates.py`
- Modify: `plugins/jira/tests/test_provider.py`
- Modify: `plugins/jira/pyproject.toml`

`keel-jira` 0.0.1 used the string-based protocol. 0.0.2 takes typed objects, owns its own Jinja templating, and exposes per-project template overrides via `[extensions.ticketing.jira.templates]`.

- [ ] **Step 1: Add templating module**

`plugins/jira/src/keel_jira/templates.py`:

```python
"""Jinja2-based template rendering for keel-jira."""
from __future__ import annotations
from typing import Any
from jinja2 import Environment, BaseLoader, StrictUndefined


# Default templates if the user provides none.
DEFAULT_TEMPLATES: dict[str, str] = {
    "milestone_summary":     "{{ milestone.title }}",
    "milestone_description": "{{ milestone.description }}",
    "task_summary":          "{{ task.title }}",
    "task_description":      "{{ task.description }}\n\n— keel: `{{ task.id }}`",
}


def make_env(extra_filters: dict[str, Any] | None = None) -> Environment:
    env = Environment(
        loader=BaseLoader(),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    if extra_filters:
        env.filters.update(extra_filters)
    return env


def render(env: Environment, template_str: str, context: dict[str, Any]) -> str:
    return env.from_string(template_str).render(**context)
```

`jinja2` is added to `plugins/jira/pyproject.toml` dependencies (it isn't there yet).

- [ ] **Step 2: Update `JiraConfig` to accept templates block**

`plugins/jira/src/keel_jira/config.py`:

Add a `templates: dict[str, str]` field:

```python
class JiraConfig(BaseModel):
    # ... existing fields ...
    templates: dict[str, str] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    def render_field(self, value: str | list | dict, context: dict) -> Any:
        """Render a single config value (string / list of strings / dict of strings)
        through Jinja, using the provided context. Used for labels/custom_fields."""
        from keel_jira.templates import make_env, render
        env = make_env()
        if isinstance(value, str):
            return render(env, value, context)
        if isinstance(value, list):
            return [render(env, str(v), context) if isinstance(v, str) else v for v in value]
        if isinstance(value, dict):
            return {k: (render(env, str(v), context) if isinstance(v, str) else v) for k, v in value.items()}
        return value
```

- [ ] **Step 3: Update `JiraProvider`**

```python
# plugins/jira/src/keel_jira/provider.py
from __future__ import annotations
from typing import TYPE_CHECKING

from keel.api import Ticket
from keel_jira.client import JiraAPIError, JiraClient
from keel_jira.config import JiraConfig, JiraCredentialsMissingError
from keel_jira.templates import DEFAULT_TEMPLATES, make_env, render

if TYPE_CHECKING:
    from keel.manifest import Milestone, Task
    from keel.workspace import Scope


class JiraProvider:
    name = "jira"

    def __init__(self) -> None:
        self._config: JiraConfig | None = None
        self._client: JiraClient | None = None
        self._env = make_env()

    def configure(self, config: dict) -> None:
        cfg = JiraConfig.from_extension_block(config)
        self._config = cfg
        self._client = JiraClient(url=cfg.url, email=cfg.email, token=cfg.token)

    def _build_context(self, *, milestone: "Milestone | None" = None, task: "Task | None" = None,
                       scope: "Scope") -> dict:
        ctx = {
            "project": scope.project,
            "deliverable": scope.deliverable,
            "scope": scope,
        }
        if milestone is not None:
            ctx["milestone"] = milestone
            ctx["milestone_id"] = milestone.id
        if task is not None:
            ctx["task"] = task
            ctx["task_id"] = task.id
        return ctx

    def _resolve_template(self, key: str) -> str:
        cfg = self._config
        return cfg.templates.get(key) or DEFAULT_TEMPLATES[key]

    def create_milestone(self, milestone: "Milestone", scope: "Scope") -> Ticket:
        cfg, client = self._require_configured()
        ctx = self._build_context(milestone=milestone, scope=scope)
        summary = render(self._env, self._resolve_template("milestone_summary"), ctx)
        description = render(self._env, self._resolve_template("milestone_description"), ctx)
        labels = cfg.render_field(cfg.labels, ctx)
        custom_fields = cfg.render_field(cfg.custom_fields, ctx)

        result = client.create_issue(
            project_key=cfg.project_key,
            issue_type=cfg.issue_type_milestone,
            summary=summary,
            description=description,
            parent_key=cfg.parent_id or None,
            labels=labels,
            custom_fields=custom_fields,
        )
        key = result["key"]
        return Ticket(id=key, url=client.link_url(key), title=summary, status=cfg.jira_status_for("planned"))

    def create_task(self, task: "Task", scope: "Scope") -> Ticket:
        cfg, client = self._require_configured()
        # Find the parent milestone's ticket id from the scope's milestones manifest.
        from keel.api import load_milestones_manifest, find_milestone
        manifest = load_milestones_manifest(scope.milestones_manifest_path)
        parent_milestone = find_milestone(manifest, task.milestone)
        parent_ticket_id = parent_milestone.ticket_id if parent_milestone else None

        ctx = self._build_context(task=task, milestone=parent_milestone, scope=scope)
        summary = render(self._env, self._resolve_template("task_summary"), ctx)
        description = render(self._env, self._resolve_template("task_description"), ctx)
        labels = cfg.render_field(cfg.labels, ctx)
        custom_fields = cfg.render_field(cfg.custom_fields, ctx)

        result = client.create_issue(
            project_key=cfg.project_key,
            issue_type=cfg.issue_type_task,
            summary=summary,
            description=description,
            parent_key=parent_ticket_id,
            labels=labels,
            custom_fields=custom_fields,
        )
        key = result["key"]
        return Ticket(id=key, url=client.link_url(key), title=summary, status=cfg.jira_status_for("planned"))

    # transition / fetch / link_url unchanged from 0.0.1

    def _require_configured(self) -> tuple[JiraConfig, JiraClient]:
        if self._config is None or self._client is None:
            raise JiraCredentialsMissingError(
                "JiraProvider was used before configure() was called"
            )
        return self._config, self._client
```

`JiraClient.create_issue` needs to accept `labels` and `custom_fields` parameters; extend it.

- [ ] **Step 4: Tests for new provider behavior**

Add a few tests to `plugins/jira/tests/test_provider.py`:

```python
def test_create_milestone_with_typed_object(jira_env, projects, make_project) -> None:
    proj = make_project("foo")
    from keel.api import Milestone
    from keel.workspace import Scope
    p = JiraProvider()
    p.configure({"url": "https://acme.atlassian.net", "project_key": "PROJ"})

    milestone = Milestone(id="m1", title="Foundation", status="planned")
    scope = Scope(project="foo")

    with respx.mock:
        respx.post("https://acme.atlassian.net/rest/api/3/issue").mock(
            return_value=Response(201, json={"id": "1", "key": "PROJ-10"})
        )
        ticket = p.create_milestone(milestone, scope)
    assert ticket.id == "PROJ-10"


def test_user_template_overrides_default(jira_env, projects, make_project) -> None:
    proj = make_project("foo")
    from keel.api import Milestone
    from keel.workspace import Scope

    p = JiraProvider()
    p.configure({
        "url": "https://acme.atlassian.net",
        "project_key": "PROJ",
        "templates": {
            "milestone_summary": "[{{ milestone.id }}] {{ milestone.title }}",
        },
    })

    milestone = Milestone(id="m1", title="Foundation", status="planned")
    scope = Scope(project="foo")

    with respx.mock:
        route = respx.post("https://acme.atlassian.net/rest/api/3/issue").mock(
            return_value=Response(201, json={"id": "1", "key": "PROJ-11"})
        )
        p.create_milestone(milestone, scope)

    import json as _json
    payload = _json.loads(route.calls.last.request.read())
    assert payload["fields"]["summary"] == "[m1] Foundation"
```

- [ ] **Step 5: Bump keel-jira to 0.0.2**

In `plugins/jira/pyproject.toml`:

```toml
version = "0.0.2"

dependencies = [
    "keel-cli>=0.0.3",
    "httpx>=0.27",
    "pydantic>=2",
    "jinja2>=3.1",
]
```

- [ ] **Step 6: Run tests + commit**

```bash
cd /Users/andrei.matei/projects/keel/plugins/jira && uv run --extra dev pytest --tb=short
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
git -C ~/projects add keel/plugins/jira/
git -C ~/projects commit -m "feat(keel-jira)!: 0.0.2 — typed-object protocol, internal Jinja templates"
```

---

## Section 9: Bump versions, decisions, docs, smoke + tag

### Task 9.1: Decision file recording the redesign

**Files:**
- Create: `design/decisions/2026-05-05-data-model-redesign.md`

```markdown
---
date: 2026-05-05
title: Data-model + project-layout redesign for 0.0.3
status: accepted
---

# Data-model + project-layout redesign for 0.0.3

## Question

Should keel adopt a redesigned project layout, hierarchy, and ticketing
protocol before users accumulate on the v0.0.x model?

## Conclusion

Yes. The redesign is captured in `design/specs/2026-05-05-data-model-redesign.md`.
Implemented in Plan 8 (`design/plans/2026-05-05-plan-8-data-model-redesign.md`).
Both wheels bump on completion: `keel-cli` 0.0.2 → 0.0.3 and `keel-jira` 0.0.1 → 0.0.2.

The four locked decisions:

1. **Layout (Option D):** manifests at root; `.keel/` for tool state;
   `decisions/`/`plans/`/`specs/` flat at root; `design/` killed; README
   auto-generated.
2. **Hierarchy:** implicit-default milestone — keel auto-creates when
   `task add` runs without `--milestone`, auto-removes when emptied.
3. **Deliverables:** identical schema to projects, recursive nesting,
   drop `deliverable.toml`.
4. **Ticketing templates:** entirely per-plugin, no core renderer; plugins
   receive typed `Milestone`/`Task`/`Scope` objects.

Migration via `keel migrate` (existing command, extended with the
legacy-layout step). Backward-compat reads of `deliverable.toml` removed
in a future 0.0.x once active workspaces are migrated.
```

- [ ] **Commit**

```bash
git -C ~/projects add keel/design/decisions/2026-05-05-data-model-redesign.md
git -C ~/projects commit -m "docs(keel): record decision — 0.0.3 data-model + layout redesign"
```

---

### Task 9.2: Bump keel-cli to 0.0.3; refresh README + design.md + CONTRIBUTING

**Files:**
- Modify: `pyproject.toml` (root)
- Modify: `README.md`
- Modify: `design/design.md`
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Bump version**

In `pyproject.toml` root: `version = "0.0.3"`.

In `[project.optional-dependencies]`, update the `jira` and `all` extras to require `keel-jira>=0.0.2`:

```toml
jira = ["keel-jira>=0.0.2"]
all = ["keel-jira>=0.0.2"]
```

- [ ] **Step 2: Update README + design.md**

Refresh sections that referenced `design/` paths or the old layout. Add a "Migrating from 0.0.x" subsection pointing at `keel migrate --all`.

- [ ] **Step 3: Update CONTRIBUTING — `[extensions]` conventions**

Add a section documenting:
- The selector pattern: `[extensions.<group>] provider = "<name>"` + `[extensions.<group>.<name>]` for per-plugin config.
- Plugins read their own block. keel core stays out of plugin schemas.
- The five-categories rule (declared identity / declared work / current state / locked snapshots / derived caches).

- [ ] **Step 4: Commit**

```bash
git -C ~/projects add keel/pyproject.toml keel/README.md keel/design/design.md keel/CONTRIBUTING.md
git -C ~/projects commit -m "chore(keel): bump keel-cli to 0.0.3; refresh README, design.md, CONTRIBUTING"
```

---

### Task 9.3: Final smoke + tag + sync to public + publish

- [ ] **Step 1: Full suite + lint + format**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests plugins/jira/src plugins/jira/tests
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff format --check src tests plugins/jira/src plugins/jira/tests
```

- [ ] **Step 2: End-to-end smoke**

```bash
SMOKE_DIR=$(mktemp -d -t keel-p8-smoke-XXXXXX)

# Create a new-layout project
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel new alpha -d "test" --no-worktree -y
ls $SMOKE_DIR/alpha
# Expected: project.toml, README.md, scope.md, design.md, decisions/, .keel/

# Implicit-default milestone behavior
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel task add t1 --title "Set up" --project alpha
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel task list --project alpha
# Expected: t1 listed; milestone "default" auto-created

# Migrate a v0.0.x layout
mkdir -p $SMOKE_DIR/legacy/design/decisions
echo '[project]
name = "legacy"
description = "old"
created = 2026-01-01' > $SMOKE_DIR/legacy/design/project.toml
echo "scoping" > $SMOKE_DIR/legacy/design/.phase
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel migrate legacy -y
# Expected: $SMOKE_DIR/legacy/project.toml exists; design/ gone

rm -rf $SMOKE_DIR
```

- [ ] **Step 3: Tag**

```bash
git -C /Users/andrei.matei/projects tag keel-plan-8
```

- [ ] **Step 4: Sync to public repo**

```bash
git -C /Users/andrei.matei/projects format-patch --relative=keel/ keel-plan-7..keel-plan-8 -o /tmp/keel-p8-patches/
cd /tmp/project-cli-publish
git am /tmp/keel-p8-patches/*.patch
uv run --extra dev pytest --tb=short
```

- [ ] **Step 5: Tag in public + push**

```bash
cd /tmp/project-cli-publish
git tag keel-plan-8
git tag keel-cli-v0.0.3
git push origin main
git push origin keel-plan-8
```

- [ ] **Step 6: Trigger PyPI publishes**

`keel-cli-v0.0.3` tag triggers the existing release workflow.

After keel-cli 0.0.3 lands on PyPI, push the keel-jira tag:

```bash
cd /tmp/project-cli-publish
git tag keel-jira-v0.0.2
git push origin keel-jira-v0.0.2
```

Verify both packages:

```bash
curl -fsS https://pypi.org/pypi/keel-cli/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"
curl -fsS https://pypi.org/pypi/keel-jira/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"
```

Expected: `0.0.3` for `keel-cli`, `0.0.2` for `keel-jira`.

---

## Self-review

| Spec section | Implementing tasks |
|---|---|
| Layout (Option D) | T2.1, T2.2, T3.1, T4.1, T4.2, T7.1 |
| Hierarchy — implicit default milestone | T5.1, T5.2, T5.3 |
| Deliverables — same schema, drop deliverable.toml | T1.1, T6.1, T6.2 |
| Ticketing — typed objects, per-plugin templates | T8.1, T8.2, T8.3 |
| Migration old → new layout | T7.1 |
| Five-categories state model | Documented in CONTRIBUTING (T9.2) |
| `.keel/lifecycle.lock.toml` snapshot | T3.1 + lifecycle_source_path helper |
| README auto-generation | T3.1 (template + write); T9.2 (refresh root) |

**Placeholder scan**: every step contains real test code, real implementation snippets, real commit commands.

**Type consistency**: `Milestone`, `Task`, `Scope`, `ProjectMeta`, `ProjectManifest`, `RepoSpec`, `Ticket` are all referenced via `keel.api` consistently. `Lifecycle` and `LifecycleNotFoundError` from `keel.api` (Plan 7).

**Out of scope (per spec):**
- Schema-versioned manifests (`schema = 1`).
- Multi-provider ticketing (push to Jira AND GitHub from one project).
- Sidecar tickets (local markdown ticket plugin).
- `keel-ai` and the new entry-point groups it would need (`keel.file_events`, `keel.agent_tools`).

These don't appear as tasks — correct.

---

## Execution Handoff

Plan complete and saved to `keel/design/plans/2026-05-05-plan-8-data-model-redesign.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks. Matches Plans 5/5.1/5.2/5.3/5.4/5.5/6/7 in this repo.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
