# Plan 6: Extensibility hardening + phase guardrails

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Resolve two long-standing gaps surfaced by the inspection: (a) phase transitions have zero guardrails — a user can jump from `scoping` to `done` with no warning; (b) the plugin contract has no event surface — plugins can register commands and ticket providers but can't react to anything keel does. This plan adds preflight checks for phase transitions, two new entry-point groups for plugins, plugin-introspection commands, and a manifest validator.

**Architecture:**

- New module `keel.preflights` with built-in preflight rules + a `PhasePreflight` Protocol.
- `keel phase --next` and `keel phase <name>` run preflights; warnings prompt-to-confirm, blockers exit non-zero. `--strict` upgrades warnings to blockers; `--force` skips both.
- `keel phase --list-next [--json]` for machine-readable transition queries.
- New entry-point groups: `keel.phase_preflights` (plugins add rules), `keel.phase_transitions` (plugins react to successful transitions).
- New `keel plugin` command group: `list`, `doctor`.
- New `keel manifest validate <path>` to lint a TOML schema offline.
- Customizable phase lifecycles (DSL/templates) are out of scope — Plan 6.5 territory after a brainstorm.

**Tech Stack:** Same as Plan 5.5.

---

## Pre-requisites

- Plan 5.5 complete; tag `keel-plan-5.5` exists.
- 400 tests pass on `main`.
- Ruff + ruff format clean.

---

## Section 1: Preflight framework

### Task 1.1: `PhasePreflight` Protocol + `PreflightResult` dataclass

**Files:**
- Create: `src/keel/preflights/__init__.py`
- Create: `src/keel/preflights/base.py`
- Modify: `src/keel/api.py`

- [ ] **Step 1: Implement**

`src/keel/preflights/base.py`:

```python
"""Phase preflight protocol and result type.

Preflights run before a phase transition and may emit warnings or blockers.
- A warning prompts the user to confirm. `--force` skips warnings.
- A blocker exits non-zero. `--force` overrides blockers too.
- `--strict` upgrades warnings to blockers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from keel.workspace import Scope


@dataclass(frozen=True)
class PreflightResult:
    """Outcome of running a preflight check.

    `warnings` are advisory; `blockers` are fatal unless --force is passed.
    """

    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True iff the preflight emitted neither warnings nor blockers."""
        return not self.warnings and not self.blockers


@runtime_checkable
class PhasePreflight(Protocol):
    """A pluggable check run before a phase transition.

    Implementations decide internally whether they care about a given
    (from_phase, to_phase) pair — return an empty result to opt out.
    """

    name: str

    def check(self, scope: "Scope", from_phase: str, to_phase: str) -> PreflightResult:
        """Inspect the project at `scope` and return any warnings/blockers
        for the proposed transition.
        """
        ...
```

`src/keel/preflights/__init__.py`:

```python
"""Phase preflight framework — built-in rules + plugin discovery."""
from __future__ import annotations

from keel.preflights.base import PhasePreflight, PreflightResult
from keel.preflights.builtin import builtin_preflights
from keel.preflights.registry import iter_preflights

__all__ = [
    "PhasePreflight",
    "PreflightResult",
    "builtin_preflights",
    "iter_preflights",
]
```

(`builtin_preflights` and `iter_preflights` come in Tasks 1.2 and 4.1.)

- [ ] **Step 2: Add to `keel.api`**

```python
from keel.preflights import PhasePreflight, PreflightResult
```
Add to `__all__` under a new `# Preflights` section.

- [ ] **Step 3: Tests**

`tests/test_preflights.py`:

```python
"""Tests for the preflight framework."""
from keel.preflights import PreflightResult, PhasePreflight


def test_preflight_result_ok_when_empty() -> None:
    r = PreflightResult()
    assert r.ok is True


def test_preflight_result_not_ok_with_warning() -> None:
    r = PreflightResult(warnings=["x"])
    assert r.ok is False


def test_preflight_result_not_ok_with_blocker() -> None:
    r = PreflightResult(blockers=["x"])
    assert r.ok is False


def test_preflight_protocol_is_runtime_checkable() -> None:
    class FakePreflight:
        name = "fake"
        def check(self, scope, from_phase, to_phase):
            return PreflightResult()

    assert isinstance(FakePreflight(), PhasePreflight)
```

- [ ] **Step 4: Run tests + commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/preflights/ keel/src/keel/api.py keel/tests/test_preflights.py && git -C /Users/andrei.matei/projects commit -m "feat(keel): add PhasePreflight protocol + PreflightResult"
```

---

### Task 1.2: Built-in preflight rules for the default lifecycle

**Files:**
- Create: `src/keel/preflights/builtin.py`
- Modify: `src/keel/preflights/__init__.py`
- Create: `tests/test_preflights_builtin.py`

The 5 built-in rules:

| Transition | Check | Severity |
|---|---|---|
| `scoping → designing` | `scope.md` differs from fresh template render | warning |
| `designing → poc` | `design.md` differs from fresh template AND ≥1 decision file | warning each |
| `poc → implementing` | ≥1 milestone exists | blocker |
| `implementing → shipping` | every milestone is `done` or `cancelled` | warning |
| `shipping → done` | all milestones `done`/`cancelled` AND all worktrees clean | blocker for milestones, warning for dirty worktrees |

Backward transitions and `* → cancelled` are not gated.

- [ ] **Step 1: Implement**

```python
"""Built-in preflight rules for keel's default phase lifecycle."""
from __future__ import annotations

from keel import templates
from keel.preflights.base import PhasePreflight, PreflightResult
from keel.workspace import Scope


def _template_diff(scope: Scope, filename: str, template_name: str) -> bool:
    """True if the file on disk differs from a fresh template render."""
    path = scope.design_dir / filename
    if not path.is_file():
        return True  # missing file is a "difference" — preflight will flag it elsewhere if it matters
    actual = path.read_text()
    rendered = templates.render(
        template_name,
        name=scope.project,
        description="",  # placeholder; only used to detect "still template"
    )
    return actual.strip() != rendered.strip()


class _ScopeEditedPreflight:
    name = "scope-md-edited"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if (from_phase, to_phase) != ("scoping", "designing"):
            return PreflightResult()
        if not _template_diff(scope, "scope.md", "scope_md.j2"):
            return PreflightResult(warnings=["scope.md is still the template scaffold"])
        return PreflightResult()


class _DesignEditedPreflight:
    name = "design-md-edited"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if (from_phase, to_phase) != ("designing", "poc"):
            return PreflightResult()
        warns: list[str] = []
        if not _template_diff(scope, "design.md", "design_md.j2"):
            warns.append("design.md is still the template scaffold")
        decisions = scope.decisions_dir
        if not decisions.is_dir() or not any(decisions.glob("*.md")):
            warns.append("no decision records under design/decisions/")
        return PreflightResult(warnings=warns)


class _MilestoneExistsPreflight:
    name = "milestone-exists"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if (from_phase, to_phase) != ("poc", "implementing"):
            return PreflightResult()
        from keel.manifest import load_milestones_manifest
        m = load_milestones_manifest(scope.milestones_manifest_path)
        if not m.milestones:
            return PreflightResult(blockers=["no milestones defined; add one with 'keel milestone add'"])
        return PreflightResult()


class _MilestonesCompletePreflight:
    name = "milestones-complete"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if to_phase not in ("shipping", "done"):
            return PreflightResult()
        from keel.manifest import load_milestones_manifest
        m = load_milestones_manifest(scope.milestones_manifest_path)
        unfinished = [
            ms.id for ms in m.milestones if ms.status not in ("done", "cancelled")
        ]
        if not unfinished:
            return PreflightResult()
        msg = f"unfinished milestones: {', '.join(unfinished)}"
        if to_phase == "done":
            return PreflightResult(blockers=[msg])
        return PreflightResult(warnings=[msg])


class _WorktreesCleanPreflight:
    name = "worktrees-clean"

    def check(self, scope: Scope, from_phase: str, to_phase: str) -> PreflightResult:
        if (from_phase, to_phase) != ("shipping", "done"):
            return PreflightResult()
        from keel import git_ops
        from keel.manifest import load_project_manifest
        try:
            pm = load_project_manifest(scope.manifest_path)
        except Exception:
            return PreflightResult()
        unit_dir = scope.unit_dir
        dirty = []
        for repo in pm.repos:
            wt = unit_dir / repo.worktree
            if wt.is_dir() and git_ops.is_worktree_dirty(wt):
                dirty.append(str(wt))
        if dirty:
            return PreflightResult(warnings=[f"dirty worktrees: {', '.join(dirty)}"])
        return PreflightResult()


def builtin_preflights() -> list[PhasePreflight]:
    """Return the default-lifecycle built-in preflights."""
    return [
        _ScopeEditedPreflight(),
        _DesignEditedPreflight(),
        _MilestoneExistsPreflight(),
        _MilestonesCompletePreflight(),
        _WorktreesCleanPreflight(),
    ]
```

NOTE: `scope.unit_dir` may need adding if not present. Check workspace.py — if not, use `scope.design_dir.parent`. Same for `scope.manifest_path` (already exists per Plan 4.5).

- [ ] **Step 2: Tests**

Test each rule's positive and negative paths. ~10 tests.

```python
def test_scope_edited_warns_when_template(projects, make_project) -> None:
    proj = make_project("foo")
    scope = ...  # construct from project name
    r = _ScopeEditedPreflight().check(scope, "scoping", "designing")
    assert "still the template" in (r.warnings + r.blockers)[0]


def test_scope_edited_clean_when_modified(projects, make_project) -> None:
    proj = make_project("foo")
    (proj / "design" / "scope.md").write_text("# foo\n\nReal content here.")
    scope = ...
    r = _ScopeEditedPreflight().check(scope, "scoping", "designing")
    assert r.ok


def test_milestone_exists_blocks_when_empty(projects, make_project) -> None:
    proj = make_project("foo")
    scope = ...
    r = _MilestoneExistsPreflight().check(scope, "poc", "implementing")
    assert r.blockers


def test_milestone_exists_passes_when_present(projects, make_project) -> None:
    # add a milestone via manifest write
    ...


# Similar for design-edited, milestones-complete, worktrees-clean.
```

Use the `make_project` fixture. For the `Scope` constructor, see how existing tests build it (`Scope(project="foo")` perhaps).

- [ ] **Step 3: Run tests + commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/preflights/builtin.py keel/src/keel/preflights/__init__.py keel/tests/test_preflights_builtin.py && git -C /Users/andrei.matei/projects commit -m "feat(keel): add built-in preflight rules for default phase lifecycle"
```

---

## Section 2: Wire preflights into `keel phase`

### Task 2.1: Run preflights on phase transitions; add `--strict` and `--force`

**Files:**
- Modify: `src/keel/commands/phase.py`
- Modify: `tests/commands/test_phase.py`

- [ ] **Step 1: Update `cmd_phase`**

Read the existing `cmd_phase`. The current flow (rough):
1. Resolve scope.
2. Read current phase.
3. If `--next` or explicit phase given, validate transition.
4. Write new phase to `.phase`.
5. Auto-create a decision file documenting the transition.

Insert a preflight step between (3) and (4):

```python
from keel.preflights import iter_preflights, PreflightResult

if not (force or current == target):  # skip when forcing or no-op
    accumulated = PreflightResult()
    for pf in iter_preflights():
        result = pf.check(scope, current, target)
        accumulated = PreflightResult(
            warnings=accumulated.warnings + result.warnings,
            blockers=accumulated.blockers + result.blockers,
        )
    if strict:
        # Upgrade all warnings to blockers
        accumulated = PreflightResult(
            warnings=[],
            blockers=accumulated.warnings + accumulated.blockers,
        )
    if accumulated.blockers:
        for b in accumulated.blockers:
            out.error(f"preflight blocker: {b}", code=ErrorCode.PREFLIGHT_BLOCKED)
        out.fail(
            "phase transition blocked by preflight checks (use --force to override)",
            code=ErrorCode.PREFLIGHT_BLOCKED,
        )
    if accumulated.warnings:
        for w in accumulated.warnings:
            out.warn(f"preflight: {w}")
        confirm_destructive(
            f"Continue with phase {current} -> {target}? (use --strict to block on warnings)",
            yes=yes,
        )
```

Use `out.warn` from Plan 5.2. Use `confirm_destructive` from `keel.prompts`.

Add new typer parameters:
```python
strict: bool = typer.Option(False, "--strict", help="Treat preflight warnings as blockers."),
force: bool = typer.Option(False, "--force", help="Skip preflight checks entirely."),
yes: bool = typer.Option(False, "-y", "--yes", help="Skip the warning confirmation prompt."),
```

- [ ] **Step 2: New ErrorCode**

In `src/keel/errors.py`, add:
```python
PREFLIGHT_BLOCKED = "preflight_blocked"
```

- [ ] **Step 3: Tests**

```python
def test_phase_next_warns_on_template_scope(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    # Don't edit scope.md → should warn
    result = runner.invoke(app, ["phase", "--next", "-y"])
    assert result.exit_code == 0
    assert "scope.md" in result.stderr.lower()


def test_phase_strict_blocks_on_warning(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["phase", "--next", "--strict"])
    assert result.exit_code != 0


def test_phase_force_skips_preflight(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["phase", "--next", "--force"])
    assert result.exit_code == 0


def test_phase_blocker_blocks_without_force(projects, make_project, monkeypatch) -> None:
    """poc → implementing without milestones blocks."""
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    # Force ahead through scoping→designing→poc, then try implementing without milestones
    runner.invoke(app, ["phase", "designing", "--force"])
    runner.invoke(app, ["phase", "poc", "--force"])
    result = runner.invoke(app, ["phase", "implementing", "--strict"])
    assert result.exit_code != 0
    assert "milestone" in result.stderr.lower()
```

- [ ] **Step 4: Run tests + commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/phase.py keel/src/keel/errors.py keel/tests/commands/test_phase.py && git -C /Users/andrei.matei/projects commit -m "feat(keel): wire preflights into 'keel phase' with --strict/--force/-y"
```

---

### Task 2.2: `keel phase --list-next` for machine-readable transition queries

**Files:**
- Modify: `src/keel/commands/phase.py`
- Modify: `tests/commands/test_phase.py`

- [ ] **Step 1: Add `--list-next` flag**

```python
list_next: bool = typer.Option(
    False, "--list-next",
    help="Print the valid next phase(s) from the current state and exit (no transition).",
),
```

When `list_next=True`:

```python
if list_next:
    next_p = next_phase(current)
    nexts = [next_p] if next_p is not None else []
    if json_mode:
        out.result({"current": current, "next": nexts})
    else:
        if nexts:
            out.info(f"Current: {current} → next: {', '.join(nexts)}")
        else:
            out.info(f"Current: {current} (end of lifecycle)")
    return
```

The list-of-list shape future-proofs against multi-successor lifecycles (Plan 6.5).

- [ ] **Step 2: Tests**

```python
def test_phase_list_next_default(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["phase", "--list-next", "--json"])
    data = json.loads(result.stdout)
    assert data == {"current": "scoping", "next": ["designing"]}


def test_phase_list_next_at_end(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["phase", "done", "--force"])
    result = runner.invoke(app, ["phase", "--list-next", "--json"])
    data = json.loads(result.stdout)
    assert data == {"current": "done", "next": []}
```

- [ ] **Step 3: Run tests + commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/phase.py keel/tests/commands/test_phase.py && git -C /Users/andrei.matei/projects commit -m "feat(keel): add 'phase --list-next' for machine-readable transition queries"
```

---

## Section 3: Plugin entry-point groups

### Task 3.1: `keel.phase_preflights` entry-point + registry

**Files:**
- Create: `src/keel/preflights/registry.py`
- Modify: `src/keel/preflights/__init__.py`
- Add tests: `tests/test_preflights_registry.py`

Plugins register a callable that returns a `list[PhasePreflight]`. The registry merges built-ins + plugin contributions.

- [ ] **Step 1: Implement**

```python
"""Phase preflight discovery — built-in + plugin entry points.

Plugin packages declare in their pyproject.toml:

    [project.entry-points."keel.phase_preflights"]
    my_rules = "my_pkg.preflights:get_preflights"

`get_preflights` must return list[PhasePreflight].
"""
from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import entry_points

from keel.preflights.base import PhasePreflight
from keel.preflights.builtin import builtin_preflights


def iter_preflights() -> Iterable[PhasePreflight]:
    """Yield all preflights (built-in first, then plugins)."""
    yield from builtin_preflights()
    for ep in entry_points(group="keel.phase_preflights"):
        try:
            getter = ep.load()
            yielded = getter()
        except Exception:
            continue
        for pf in yielded:
            yield pf
```

- [ ] **Step 2: Add to `keel.api`**

Already exposed via `keel.preflights` (which is in `keel.api`). Confirm `iter_preflights` is accessible.

- [ ] **Step 3: Tests**

```python
from unittest.mock import MagicMock, patch
from keel.preflights import iter_preflights
from keel.preflights.builtin import builtin_preflights


def test_iter_preflights_returns_builtins() -> None:
    with patch("keel.preflights.registry.entry_points", return_value=[]):
        items = list(iter_preflights())
    assert len(items) == len(builtin_preflights())


def test_iter_preflights_includes_plugins() -> None:
    class FakePreflight:
        name = "fake"
        def check(self, scope, from_phase, to_phase):
            from keel.preflights import PreflightResult
            return PreflightResult()

    fake_ep = MagicMock()
    fake_ep.load.return_value = lambda: [FakePreflight()]
    with patch("keel.preflights.registry.entry_points", return_value=[fake_ep]):
        items = list(iter_preflights())
    names = [p.name for p in items]
    assert "fake" in names
```

- [ ] **Step 4: Run tests + commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/preflights/registry.py keel/src/keel/preflights/__init__.py keel/tests/test_preflights_registry.py && git -C /Users/andrei.matei/projects commit -m "feat(keel): add keel.phase_preflights entry-point group"
```

---

### Task 3.2: `keel.phase_transitions` event hook

**Files:**
- Create: `src/keel/phase_events.py`
- Modify: `src/keel/commands/phase.py`
- Add tests: `tests/test_phase_events.py`

Plugins register a callable that runs AFTER a successful phase transition. Pure side effect — return value ignored. Errors are caught and warned (don't fail the transition).

- [ ] **Step 1: Implement**

```python
"""Phase transition event hooks.

Plugin packages declare in their pyproject.toml:

    [project.entry-points."keel.phase_transitions"]
    my_hook = "my_pkg.hooks:on_transition"

The function receives (scope, from_phase, to_phase). Errors are caught and
logged via out.warn — a failing hook will not roll back the phase change.
"""
from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from keel.output import Output
    from keel.workspace import Scope

PhaseTransitionHook = Callable[["Scope", str, str], None]


def iter_phase_transition_hooks() -> list[PhaseTransitionHook]:
    """Return all registered phase-transition hooks."""
    out: list[PhaseTransitionHook] = []
    for ep in entry_points(group="keel.phase_transitions"):
        try:
            hook = ep.load()
        except Exception:
            continue
        out.append(hook)
    return out


def fire_phase_transition(scope: "Scope", from_phase: str, to_phase: str, *, out: "Output") -> None:
    """Fire all registered post-transition hooks. Warns on failures; never raises."""
    for hook in iter_phase_transition_hooks():
        try:
            hook(scope, from_phase, to_phase)
        except Exception as e:  # noqa: BLE001
            name = getattr(hook, "__name__", repr(hook))
            out.warn(f"phase-transition hook '{name}' failed: {e}")
```

- [ ] **Step 2: Wire into `cmd_phase`**

After the `.phase` file write succeeds (and after the auto-decision file is created):

```python
from keel.phase_events import fire_phase_transition

fire_phase_transition(scope, current, target, out=out)
```

- [ ] **Step 3: Add to `keel.api`**

```python
from keel.phase_events import (
    PhaseTransitionHook,
    fire_phase_transition,
    iter_phase_transition_hooks,
)
```
Add to `__all__`.

- [ ] **Step 4: Tests**

```python
from unittest.mock import MagicMock, patch
from keel.phase_events import fire_phase_transition, iter_phase_transition_hooks


def test_iter_hooks_empty_by_default() -> None:
    with patch("keel.phase_events.entry_points", return_value=[]):
        assert iter_phase_transition_hooks() == []


def test_fire_calls_each_hook() -> None:
    calls = []
    def hook_a(scope, from_, to_): calls.append(("a", from_, to_))
    def hook_b(scope, from_, to_): calls.append(("b", from_, to_))

    out_mock = MagicMock()
    with patch("keel.phase_events.iter_phase_transition_hooks", return_value=[hook_a, hook_b]):
        fire_phase_transition(scope=None, from_phase="x", to_phase="y", out=out_mock)
    assert calls == [("a", "x", "y"), ("b", "x", "y")]


def test_fire_swallows_hook_errors() -> None:
    def bad_hook(scope, from_, to_):
        raise RuntimeError("boom")
    out_mock = MagicMock()
    with patch("keel.phase_events.iter_phase_transition_hooks", return_value=[bad_hook]):
        fire_phase_transition(scope=None, from_phase="x", to_phase="y", out=out_mock)
    out_mock.warn.assert_called_once()
```

- [ ] **Step 5: Run tests + commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/phase_events.py keel/src/keel/commands/phase.py keel/src/keel/api.py keel/tests/test_phase_events.py && git -C /Users/andrei.matei/projects commit -m "feat(keel): add keel.phase_transitions entry-point group + fire_phase_transition"
```

---

## Section 4: Plugin introspection commands

### Task 4.1: `keel plugin` command group with `list` and `doctor`

**Files:**
- Create: `src/keel/commands/plugin/__init__.py`
- Create: `src/keel/commands/plugin/list.py`
- Create: `src/keel/commands/plugin/doctor.py`
- Modify: `src/keel/app.py`
- Add tests: `tests/commands/plugin/test_list.py`, `tests/commands/plugin/test_doctor.py`

`keel plugin list` enumerates installed plugins across all 4 entry-point groups (`keel.commands`, `keel.ticket_providers`, `keel.phase_preflights`, `keel.phase_transitions`).

`keel plugin doctor` validates that the current project's plugin configuration is consistent: every `[extensions.X]` block has a corresponding installed plugin; ticketing config can be loaded; preflights run without errors against the current scope.

- [ ] **Step 1: Scaffold subpackage**

`src/keel/commands/plugin/__init__.py`:

```python
"""`keel plugin ...` command group."""
from __future__ import annotations

import typer

app = typer.Typer(
    name="plugin",
    help="Inspect installed keel plugins and their configuration.",
    no_args_is_help=True,
)

from keel.commands.plugin.list import cmd_list  # noqa: E402

app.command(name="list")(cmd_list)

from keel.commands.plugin.doctor import cmd_doctor  # noqa: E402

app.command(name="doctor")(cmd_doctor)
```

- [ ] **Step 2: Implement `list`**

```python
"""`keel plugin list` — enumerate installed keel plugins."""
from __future__ import annotations

from importlib.metadata import entry_points

import typer
from rich.table import Table

from keel.api import Output

GROUPS = [
    "keel.commands",
    "keel.ticket_providers",
    "keel.phase_preflights",
    "keel.phase_transitions",
]


def cmd_list(
    ctx: typer.Context,
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """List installed plugins across all keel entry-point groups."""
    out = Output.from_context(ctx, json_mode=json_mode)

    rows: list[dict[str, str]] = []
    for group in GROUPS:
        for ep in entry_points(group=group):
            rows.append({"group": group, "name": ep.name, "value": ep.value})

    if json_mode:
        out.result({"plugins": rows})
        return

    if not rows:
        out.result(None, human_text="(no plugins installed)")
        return

    table = Table()
    table.add_column("Group")
    table.add_column("Name")
    table.add_column("Module")
    for r in rows:
        table.add_row(r["group"], r["name"], r["value"])
    out.print_rich(table)
```

- [ ] **Step 3: Implement `doctor`**

```python
"""`keel plugin doctor` — validate plugin configuration for the current project."""
from __future__ import annotations

import typer

from keel.api import (
    ErrorCode,
    Output,
    iter_preflights,
    load_project_manifest,
    resolve_cli_scope,
)
from keel.ticketing import get_provider_for_project
from keel.ticketing.registry import list_providers


def cmd_doctor(
    ctx: typer.Context,
    project: str | None = typer.Option(
        None, "--project", "-p", help="Project name. Auto-detected from CWD if omitted.",
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Validate plugin configuration for the current project."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, None, out=out)
    pm = load_project_manifest(scope.manifest_path)

    findings: list[dict[str, str]] = []

    # Check ticketing config
    cfg = pm.extensions.get("ticketing", {})
    if isinstance(cfg, dict) and cfg.get("provider"):
        provider_name = cfg["provider"]
        installed = list_providers()
        if provider_name not in installed:
            findings.append({
                "level": "error",
                "area": "ticketing",
                "message": f"provider '{provider_name}' is configured but not installed (have: {installed or 'none'})",
            })
        else:
            try:
                provider = get_provider_for_project(pm)
                if provider is None:
                    findings.append({"level": "error", "area": "ticketing", "message": "provider failed to instantiate"})
            except Exception as e:
                findings.append({"level": "error", "area": "ticketing", "message": f"configure() raised: {e}"})

    # Check preflights run cleanly against the current scope
    from keel.workspace import read_phase
    current = read_phase(scope.design_dir)
    for pf in iter_preflights():
        try:
            pf.check(scope, current, current)  # self-transition should be a no-op
        except Exception as e:
            findings.append({"level": "error", "area": "preflight", "message": f"'{pf.name}' raised: {e}"})

    if json_mode:
        out.result({"findings": findings})
        return

    if not findings:
        out.result(None, human_text="OK — no issues found.")
        return

    for f in findings:
        out.warn(f"[{f['area']}] {f['message']}")
    if any(f["level"] == "error" for f in findings):
        out.fail("plugin doctor found issues", code=ErrorCode.INVALID_STATE)
```

- [ ] **Step 4: Register**

In `src/keel/app.py`:
```python
from keel.commands.plugin import app as plugin_app  # noqa: E402

app.add_typer(plugin_app, name="plugin")
```

- [ ] **Step 5: Tests**

`tests/commands/plugin/test_list.py`:

```python
import json
from typer.testing import CliRunner
from keel.app import app

runner = CliRunner()


def test_plugin_list_empty() -> None:
    result = runner.invoke(app, ["plugin", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "plugins" in data
    # In a fresh test env, no third-party plugins should be present.
    # (There may still be entries from the dev environment — assert structure only.)
    assert isinstance(data["plugins"], list)


def test_plugin_list_human_format() -> None:
    result = runner.invoke(app, ["plugin", "list"])
    assert result.exit_code == 0
```

`tests/commands/plugin/test_doctor.py`:

```python
import json
from typer.testing import CliRunner
from keel.app import app

runner = CliRunner()


def test_doctor_clean_project(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["plugin", "doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["findings"] == []


def test_doctor_flags_unknown_provider(projects, make_project, monkeypatch) -> None:
    from keel.api import load_project_manifest, save_project_manifest
    proj = make_project("foo")
    pm = load_project_manifest(proj / "design" / "project.toml")
    pm.extensions["ticketing"] = {"provider": "ghost"}
    save_project_manifest(proj / "design" / "project.toml", pm)
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["plugin", "doctor", "--json"])
    assert result.exit_code != 0
    data = json.loads(result.stdout)
    assert any("ghost" in f["message"] for f in data["findings"])
```

Need also `tests/commands/plugin/__init__.py` (empty marker).

- [ ] **Step 6: Run tests + commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/plugin/ keel/src/keel/app.py keel/tests/commands/plugin/ && git -C /Users/andrei.matei/projects commit -m "feat(keel): add 'plugin list' and 'plugin doctor' commands"
```

---

## Section 5: Manifest validator

### Task 5.1: `keel manifest validate <path>`

**Files:**
- Modify: `src/keel/commands/validate.py` OR create `src/keel/commands/manifest/validate.py`
- Add tests

`validate` already exists for project-level checks. Add a `manifest` subcommand (or a `keel manifest` group with `validate`) that lints a single TOML file against its schema.

- [ ] **Step 1: Decide command shape**

Pick `keel manifest validate <path>` (new subgroup) over extending `keel validate`. Cleaner namespace.

Create `src/keel/commands/manifest_cmd/__init__.py` (the module name `manifest` is taken by the schema package — use `manifest_cmd` or a different name):

Actually `keel manifest` as a CLI command name is fine — Typer registration name is independent of the module path. Use `src/keel/commands/manifest_cli/__init__.py` to avoid the namespace collision.

- [ ] **Step 2: Implement**

```python
"""`keel manifest ...` command group."""
from __future__ import annotations
import typer
app = typer.Typer(name="manifest", help="Lint and inspect manifest files.", no_args_is_help=True)

from keel.commands.manifest_cli.validate import cmd_validate  # noqa: E402
app.command(name="validate")(cmd_validate)
```

`src/keel/commands/manifest_cli/validate.py`:

```python
"""`keel manifest validate <path>` — lint a TOML manifest against its schema."""
from __future__ import annotations
from pathlib import Path

import typer

from keel.api import ErrorCode, Output


def cmd_validate(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Path to a project.toml, deliverable.toml, or milestones.toml."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Validate a manifest file against its Pydantic schema."""
    out = Output.from_context(ctx, json_mode=json_mode)

    if not path.is_file():
        out.fail(f"file not found: {path}", code=ErrorCode.NOT_FOUND)

    name = path.name
    if name == "project.toml":
        from keel.manifest import load_project_manifest
        loader = load_project_manifest
        kind = "project"
    elif name == "deliverable.toml":
        from keel.manifest import load_deliverable_manifest
        loader = load_deliverable_manifest
        kind = "deliverable"
    elif name == "milestones.toml":
        from keel.manifest import load_milestones_manifest
        loader = load_milestones_manifest
        kind = "milestones"
    else:
        out.fail(
            f"unsupported manifest file: {name} (expected project.toml/deliverable.toml/milestones.toml)",
            code=ErrorCode.INVALID_NAME,
        )

    try:
        loader(path)
    except Exception as e:
        out.fail(f"{kind} manifest invalid: {e}", code=ErrorCode.INVALID_STATE)

    out.result({"path": str(path), "kind": kind, "valid": True}, human_text=f"OK — {kind} manifest valid: {path}")
```

- [ ] **Step 3: Register**

In `src/keel/app.py`:
```python
from keel.commands.manifest_cli import app as manifest_app  # noqa: E402

app.add_typer(manifest_app, name="manifest")
```

- [ ] **Step 4: Tests**

```python
def test_manifest_validate_valid_project(projects, make_project) -> None:
    proj = make_project("foo")
    result = runner.invoke(app, ["manifest", "validate", str(proj / "design" / "project.toml")])
    assert result.exit_code == 0


def test_manifest_validate_invalid(projects, tmp_path) -> None:
    bad = tmp_path / "project.toml"
    bad.write_text("[project]\n# missing required fields\n")
    result = runner.invoke(app, ["manifest", "validate", str(bad)])
    assert result.exit_code != 0


def test_manifest_validate_unknown_filename(projects, tmp_path) -> None:
    foo = tmp_path / "random.toml"
    foo.write_text("")
    result = runner.invoke(app, ["manifest", "validate", str(foo)])
    assert result.exit_code != 0
```

- [ ] **Step 5: Run tests + commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/manifest_cli/ keel/src/keel/app.py keel/tests/commands/manifest_cli/ && git -C /Users/andrei.matei/projects commit -m "feat(keel): add 'keel manifest validate' to lint TOML schemas offline"
```

---

## Section 6: Documentation

### Task 6.1: CONTRIBUTING.md "Authoring a plugin" section

**Files:**
- Modify: `CONTRIBUTING.md`

Add a section near the bottom (before "License") documenting all 4 entry-point groups with a 5-line example for each.

- [ ] **Step 1: Append section**

```markdown
## Authoring a plugin

keel exposes four entry-point groups that plugins can hook into. Plugin packages
declare these in their `pyproject.toml` under `[project.entry-points]`.

### `keel.commands` — register a CLI command

```toml
[project.entry-points."keel.commands"]
my_cmd = "my_pkg.cli:register"
```

```python
# my_pkg/cli.py
import typer

def register(app: typer.Typer) -> None:
    app.command(name="my-cmd")(my_func)
```

### `keel.ticket_providers` — implement the `TicketProvider` Protocol

See `keel.ticketing.base.TicketProvider` and the reference `MockProvider`.

```toml
[project.entry-points."keel.ticket_providers"]
jira = "keel_jira.provider:JiraProvider"
```

### `keel.phase_preflights` — add preflight checks for phase transitions

```toml
[project.entry-points."keel.phase_preflights"]
my_rules = "my_pkg.preflights:get_preflights"
```

```python
# my_pkg/preflights.py
from keel.api import PhasePreflight, PreflightResult

class TicketsAcceptedPreflight:
    name = "tickets-accepted"
    def check(self, scope, from_phase, to_phase):
        if to_phase != "implementing":
            return PreflightResult()
        # ... query ticketing system ...
        return PreflightResult(warnings=[]) if accepted else PreflightResult(blockers=["..."])

def get_preflights():
    return [TicketsAcceptedPreflight()]
```

### `keel.phase_transitions` — react after a successful transition

```toml
[project.entry-points."keel.phase_transitions"]
my_hook = "my_pkg.hooks:on_transition"
```

```python
# my_pkg/hooks.py
def on_transition(scope, from_phase, to_phase):
    # Side-effect only. Errors are caught and logged via out.warn.
    print(f"transitioned {from_phase} -> {to_phase}")
```

### Testing your plugin

`pip install --extra dev keel-cli`, then in your `tests/conftest.py`:

```python
pytest_plugins = ["keel.testing"]
```

You get the `projects`, `make_project`, `make_deliverable`, `source_repo`, and
`mock_ticket_provider` fixtures for free. `MockProvider` is also re-exported
from `keel.testing` for use in non-fixture contexts.

### Inspecting installed plugins

`keel plugin list` shows everything registered across the four groups.
`keel plugin doctor` validates that the current project's `[extensions]` config
points at installed plugins and that providers can be instantiated.
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/CONTRIBUTING.md && git -C /Users/andrei.matei/projects commit -m "docs(keel): document plugin authoring (4 entry-point groups + testing)"
```

---

## Section 7: Smoke + tag + sync

### Task 7.1

- [ ] Full suite passes (~415+ tests).
- [ ] Ruff + format clean.
- [ ] Smoke: end-to-end including `phase --next` warning, `phase --strict`, `phase --list-next`, `plugin list`, `plugin doctor`, `manifest validate`.
- [ ] Tag: `git tag keel-plan-6`.
- [ ] Sync to public; push.

---

## Self-review checklist

| Inspection finding | Resolved by |
|---|---|
| No phase guardrails (`scoping → done` jumps) | Tasks 1.2, 2.1 |
| `keel phase --list-next` missing | Task 2.2 |
| `keel.phase_preflights` entry-point missing | Task 3.1 |
| `keel.phase_transitions` event hook missing | Task 3.2 |
| `keel ticketing` is empty Typer subapp with no introspection | Task 4.1 (separate `plugin` group) |
| `MockProvider` re-export was missing | already done in Plan 5.4 |
| Plugin authoring undocumented | Task 6.1 |
| No way to lint a manifest TOML offline | Task 5.1 |

## Out of scope (Plan 6.5 / later)

- Customizable phase lifecycles (templates / DSL — needs brainstorm).
- Status-mapping override for ticketing (`[ticketing.status_map]`).
- `Output.success`.
- Per-plugin config-schema declaration (plugins describe their own `[extensions.X]` shape).
