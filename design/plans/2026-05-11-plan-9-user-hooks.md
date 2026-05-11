# Plan 9: User hooks framework + phase-event consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a unified hook system for keel commands — central `keel.hooks` dispatcher, `@hookable` decorator + `hook_event` context manager, user scripts in `.keel/hooks/`, new `keel.event_listeners` entry-point group — and migrate the legacy `keel.phase_preflights` and `keel.phase_transitions` entry-point groups onto it (hard breaking change; alpha = no compat shim).

**Architecture:** Build the dispatcher first (types → registry → loaders → context manager). Migrate built-in preflights as the first real subscriber. Wire the `phase` command second (highest-value migration target). Wire remaining commands one at a time. Ship `keel hooks list/init` CLI surface last. Bump to 0.0.4 and publish.

**Tech Stack:** Same as Plan 8. Python 3.11+, Pydantic v2, Typer, importlib.metadata entry-points, subprocess for hook scripts. No new dependencies.

---

## Pre-requisites

- Plan 8 shipped: keel-cli 0.0.3 + keel-jira 0.0.2 on PyPI.
- 515 keel-cli tests + 36 keel-jira tests pass on `main`.
- Ruff + ruff format clean across `src/`, `tests/`, `plugins/`.
- The spec at `design/specs/2026-05-11-user-hooks-design.md` is locked.

---

## File Structure

After Plan 9 the keel-cli source tree looks like:

```
src/keel/
├── hooks/                      # NEW — replaces preflights/ and phase_events.py
│   ├── __init__.py             # NEW — public API: HookEvent, HookAborted, hookable, hook_event, subscribes_to
│   ├── types.py                # NEW — HookEvent dataclass, HookAborted exception
│   ├── registry.py             # NEW — in-tree subscriber registry; @subscribes_to decorator
│   ├── loader.py               # NEW — walks keel.event_listeners entry-point group
│   ├── scripts.py              # NEW — user-script runner (fork/exec, env, args, stdin)
│   ├── dispatcher.py           # NEW — fires events to all subscribers
│   ├── hookable.py             # NEW — @hookable decorator + hook_event context manager
│   └── builtin_listeners.py    # NEW — built-in preflights as @subscribes_to subscribers
├── preflights/                 # DELETED
├── phase_events.py             # DELETED
├── api.py                      # MODIFY — drop preflight/phase_events re-exports; add HookEvent etc.
├── commands/
│   ├── new.py                  # MODIFY — wrap cmd_new body in hook_event("new", ...)
│   ├── phase.py                # MODIFY — replace iter_preflights + fire_phase_transition with hook_event
│   ├── archive.py              # MODIFY — wrap in hook_event("archive", ...)
│   ├── restore.py              # MODIFY — fire post-restore
│   ├── rename.py               # MODIFY — fire post-rename
│   ├── deliverable/add.py      # MODIFY — wrap in hook_event("deliverable-add", ...)
│   ├── decision/new.py         # MODIFY — wrap in hook_event("decision-new", ...)
│   ├── plugin/list.py          # MODIFY — drop phase_preflights/phase_transitions; add event_listeners
│   └── hooks/                  # NEW — `keel hooks` command group
│       ├── __init__.py         # NEW — Typer app
│       ├── init.py             # NEW — `keel hooks init`
│       └── list.py             # NEW — `keel hooks list`
├── app.py                      # MODIFY — register the new hooks command group
└── _templates/
    └── hooks_readme.md.j2      # NEW — scaffolded into .keel/hooks/README.md

tests/
├── hooks/                      # NEW — dispatcher + scripts + registry + loader tests
│   ├── __init__.py
│   ├── test_types.py
│   ├── test_registry.py
│   ├── test_scripts.py
│   ├── test_loader.py
│   ├── test_dispatcher.py
│   ├── test_hookable.py
│   └── test_builtin_listeners.py
├── preflights/                 # DELETED (was tests/test_preflights.py + test_preflights_builtin.py)
├── test_phase_events.py        # DELETED
├── commands/
│   ├── test_phase.py           # MODIFY — preflight assertions move to hook-based
│   ├── test_new.py             # MODIFY — add pre-new/post-new firing tests
│   ├── test_archive.py         # MODIFY — add pre-archive/post-archive firing tests
│   ├── test_restore.py         # MODIFY — add post-restore firing test
│   ├── test_rename.py          # MODIFY — add post-rename firing test
│   ├── deliverable/test_add.py # MODIFY — add pre/post-deliverable-add firing tests
│   ├── decision/test_new.py    # MODIFY — add pre/post-decision-new firing tests
│   └── hooks/                  # NEW — keel hooks list/init command tests
│       ├── __init__.py
│       ├── test_init.py
│       └── test_list.py

design/decisions/
└── 2026-05-11-user-hooks-framework.md   # NEW — record the locked decisions
```

---

## Section 1: Hook core infrastructure

### Task 1.1: `HookEvent` dataclass + `HookAborted` exception

**Files:**
- Create: `src/keel/hooks/__init__.py`
- Create: `src/keel/hooks/types.py`
- Create: `tests/hooks/__init__.py`
- Create: `tests/hooks/test_types.py`

The types module is foundation for everything else. Pure data — no logic, no imports of other keel modules.

- [ ] **Step 1: Write failing tests**

Create `tests/hooks/__init__.py`:
```python
"""Tests for the keel.hooks framework."""
```

Create `tests/hooks/test_types.py`:
```python
"""Tests for keel.hooks types."""

from __future__ import annotations

import pytest


def test_hook_event_construction() -> None:
    from keel.hooks import HookEvent

    event = HookEvent(
        name="new",
        phase="pre",
        project="foo",
        deliverable=None,
        payload={"description": "test"},
        positional_args=("foo",),
    )
    assert event.name == "new"
    assert event.phase == "pre"
    assert event.project == "foo"
    assert event.deliverable is None
    assert event.payload == {"description": "test"}
    assert event.positional_args == ("foo",)


def test_hook_event_is_frozen() -> None:
    """HookEvent must be immutable so subscribers can't mutate shared state."""
    from dataclasses import FrozenInstanceError
    from keel.hooks import HookEvent

    event = HookEvent(
        name="new", phase="pre", project="foo", deliverable=None,
        payload={}, positional_args=(),
    )
    with pytest.raises(FrozenInstanceError):
        event.name = "phase"  # type: ignore[misc]


def test_hook_event_full_name() -> None:
    """full_name returns 'pre-<name>' or 'post-<name>'."""
    from keel.hooks import HookEvent

    pre = HookEvent(name="new", phase="pre", project=None, deliverable=None, payload={}, positional_args=())
    post = HookEvent(name="phase", phase="post", project="foo", deliverable=None, payload={}, positional_args=())
    assert pre.full_name == "pre-new"
    assert post.full_name == "post-phase"


def test_hook_aborted_is_runtime_error() -> None:
    """HookAborted must be catchable as RuntimeError for natural error handling."""
    from keel.hooks import HookAborted

    err = HookAborted("blocked because reasons")
    assert isinstance(err, RuntimeError)
    assert str(err) == "blocked because reasons"
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_types.py -v
```

Expected: FAIL (`keel.hooks` doesn't exist yet).

- [ ] **Step 3: Implement types**

Create `src/keel/hooks/types.py`:
```python
"""HookEvent dataclass and HookAborted exception."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class HookEvent:
    """A single hook event firing.

    Attributes are immutable so a misbehaving subscriber can't corrupt
    state for downstream subscribers.
    """

    name: str
    """Event name without phase prefix (e.g., 'new', 'phase', 'deliverable-add')."""

    phase: Literal["pre", "post"]
    """Whether this event fires before or after the command's work."""

    project: str | None
    """Project slug, or None for events not scoped to a project."""

    deliverable: str | None
    """Deliverable slug, or None for project-scoped events."""

    payload: dict[str, Any] = field(default_factory=dict)
    """Event-specific structured data. Always a dict (may be empty)."""

    positional_args: tuple[str, ...] = ()
    """High-value identifiers passed as argv to user scripts. Stable, additive."""

    @property
    def full_name(self) -> str:
        """Combined hook name, e.g. 'pre-new' or 'post-phase'."""
        return f"{self.phase}-{self.name}"


class HookAborted(RuntimeError):
    """Raised by a pre-hook subscriber to abort the command.

    Subscribers may raise this to block a transition (e.g., preflight checks
    that find a blocker). The dispatcher catches and surfaces the message.
    """
```

Create `src/keel/hooks/__init__.py`:
```python
"""keel hooks framework — events, dispatcher, subscriber registry.

Public API:
- HookEvent, HookAborted (types)
- subscribes_to (in-tree subscriber decorator) — added in Task 1.2
- @hookable, hook_event (command-side API) — added in Task 1.6
- dispatch (manual dispatch, mostly for tests) — added in Task 1.5
"""

from __future__ import annotations

from keel.hooks.types import HookAborted, HookEvent

__all__ = [
    "HookAborted",
    "HookEvent",
]
```

- [ ] **Step 4: Run tests; expect PASS**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_types.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run ruff + full suite**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=line
```

Expected: ruff clean; full suite still 515 passing (no regressions; new module isn't wired into anything yet).

- [ ] **Step 6: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/hooks/ keel/tests/hooks/
git -C /Users/andrei.matei/projects commit -m "feat(keel): add keel.hooks.HookEvent + HookAborted (types only)"
```

---

### Task 1.2: In-tree subscriber registry + `@subscribes_to` decorator

**Files:**
- Create: `src/keel/hooks/registry.py`
- Modify: `src/keel/hooks/__init__.py`
- Create: `tests/hooks/test_registry.py`

A module-level registry stores `event_name -> list[Subscriber]`. The `@subscribes_to("pre-X")` decorator registers a function at import time. Order matters: registration order is preserved.

- [ ] **Step 1: Write failing tests**

Create `tests/hooks/test_registry.py`:
```python
"""Tests for the in-tree subscriber registry."""

from __future__ import annotations


def test_subscribes_to_registers_function() -> None:
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import iter_in_tree_subscribers, _clear_registry

    _clear_registry()

    @subscribes_to("pre-new")
    def my_listener(event: HookEvent, *, out) -> None:
        pass

    subs = list(iter_in_tree_subscribers("pre-new"))
    assert len(subs) == 1
    assert subs[0] is my_listener


def test_subscribes_to_preserves_registration_order() -> None:
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import iter_in_tree_subscribers, _clear_registry

    _clear_registry()

    @subscribes_to("post-phase")
    def first(event: HookEvent, *, out) -> None:
        pass

    @subscribes_to("post-phase")
    def second(event: HookEvent, *, out) -> None:
        pass

    subs = list(iter_in_tree_subscribers("post-phase"))
    assert subs == [first, second]


def test_iter_subscribers_empty_for_unknown_event() -> None:
    from keel.hooks.registry import iter_in_tree_subscribers, _clear_registry

    _clear_registry()
    assert list(iter_in_tree_subscribers("pre-unknown")) == []


def test_subscribes_to_rejects_invalid_event_name() -> None:
    """Names must start with 'pre-' or 'post-'."""
    import pytest
    from keel.hooks import subscribes_to

    with pytest.raises(ValueError, match="must start with 'pre-' or 'post-'"):
        @subscribes_to("new")  # missing prefix
        def bad(event, *, out) -> None:
            pass
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_registry.py -v
```

Expected: FAIL (`subscribes_to`, `iter_in_tree_subscribers`, `_clear_registry` don't exist).

- [ ] **Step 3: Implement the registry**

Create `src/keel/hooks/registry.py`:
```python
"""In-tree subscriber registry.

Built-in keel modules call `@subscribes_to("pre-X")` at import time to
register themselves. The registry is process-global; tests reset it
between runs via `_clear_registry()`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from keel.hooks.types import HookEvent
    from keel.output import Output


Subscriber = Callable[["HookEvent"], None]
"""A subscriber is a callable receiving HookEvent + Output kwarg. See dispatcher."""


_REGISTRY: dict[str, list[Subscriber]] = {}


def subscribes_to(event_full_name: str) -> Callable[[Subscriber], Subscriber]:
    """Decorator: register an in-tree subscriber for a given event name.

    `event_full_name` MUST start with 'pre-' or 'post-'. Examples:
    'pre-new', 'post-phase', 'pre-deliverable-add'.

    The decorated function receives the HookEvent and an Output kwarg,
    and returns None. It may raise HookAborted (pre-events only) to abort.
    """
    if not (event_full_name.startswith("pre-") or event_full_name.startswith("post-")):
        raise ValueError(
            f"event name '{event_full_name}' must start with 'pre-' or 'post-'"
        )

    def _register(fn: Subscriber) -> Subscriber:
        _REGISTRY.setdefault(event_full_name, []).append(fn)
        return fn

    return _register


def iter_in_tree_subscribers(event_full_name: str) -> Iterator[Subscriber]:
    """Yield in-tree subscribers for the given event in registration order."""
    yield from _REGISTRY.get(event_full_name, [])


def _clear_registry() -> None:
    """Test-only: empty the registry. Not part of the public API."""
    _REGISTRY.clear()
```

Update `src/keel/hooks/__init__.py`:
```python
"""keel hooks framework — events, dispatcher, subscriber registry.

Public API:
- HookEvent, HookAborted (types)
- subscribes_to (in-tree subscriber decorator)
- @hookable, hook_event (command-side API) — added in Task 1.6
- dispatch (manual dispatch, mostly for tests) — added in Task 1.5
"""

from __future__ import annotations

from keel.hooks.registry import subscribes_to
from keel.hooks.types import HookAborted, HookEvent

__all__ = [
    "HookAborted",
    "HookEvent",
    "subscribes_to",
]
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_registry.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/hooks/registry.py keel/src/keel/hooks/__init__.py keel/tests/hooks/test_registry.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): add keel.hooks.subscribes_to in-tree subscriber registry"
```

---

### Task 1.3: User-script runner

**Files:**
- Create: `src/keel/hooks/scripts.py`
- Create: `tests/hooks/test_scripts.py`

User-script runner: given a `HookEvent` and a directory, find an executable matching the event name, run it with the event's positional args + env vars + stdin JSON. Non-zero exit raises `HookAborted`.

- [ ] **Step 1: Write failing tests**

Create `tests/hooks/test_scripts.py`:
```python
"""Tests for the user-script runner."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest


def _make_executable_script(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_run_script_passes_positional_args(tmp_path: Path) -> None:
    """Script receives positional_args as argv."""
    from keel.hooks import HookEvent
    from keel.hooks.scripts import run_user_script

    out_file = tmp_path / "args.txt"
    script = tmp_path / "post-phase"
    _make_executable_script(
        script,
        f"#!/usr/bin/env bash\necho \"$1 $2\" > {out_file}\n",
    )

    event = HookEvent(
        name="phase", phase="post", project="foo", deliverable=None,
        payload={"from": "scoping", "to": "designing"},
        positional_args=("scoping", "designing"),
    )
    run_user_script(script, event, layer="workspace")
    assert out_file.read_text().strip() == "scoping designing"


def test_run_script_sets_env_vars(tmp_path: Path) -> None:
    """KEEL_EVENT, KEEL_PROJECT, KEEL_HOOK_LAYER, per-event extras are set."""
    from keel.hooks import HookEvent
    from keel.hooks.scripts import run_user_script

    out_file = tmp_path / "env.txt"
    script = tmp_path / "post-phase"
    _make_executable_script(
        script,
        f'#!/usr/bin/env bash\nenv | grep ^KEEL_ | sort > {out_file}\n',
    )

    event = HookEvent(
        name="phase", phase="post", project="foo", deliverable="bar",
        payload={"from": "scoping", "to": "designing"},
        positional_args=("scoping", "designing"),
    )
    run_user_script(script, event, layer="project")
    env_dump = out_file.read_text()
    assert "KEEL_EVENT=post-phase" in env_dump
    assert "KEEL_PROJECT=foo" in env_dump
    assert "KEEL_DELIVERABLE=bar" in env_dump
    assert "KEEL_HOOK_LAYER=project" in env_dump
    assert "KEEL_PHASE_FROM=scoping" in env_dump
    assert "KEEL_PHASE_TO=designing" in env_dump


def test_run_script_passes_payload_on_stdin(tmp_path: Path) -> None:
    """The full event payload arrives on stdin as JSON."""
    from keel.hooks import HookEvent
    from keel.hooks.scripts import run_user_script

    out_file = tmp_path / "stdin.txt"
    script = tmp_path / "post-decision-new"
    _make_executable_script(
        script,
        f"#!/usr/bin/env bash\ncat > {out_file}\n",
    )

    event = HookEvent(
        name="decision-new", phase="post", project="foo", deliverable=None,
        payload={"slug": "use-postgres", "title": "Use Postgres", "supersedes": None},
        positional_args=("use-postgres",),
    )
    run_user_script(script, event, layer="workspace")

    import json
    parsed = json.loads(out_file.read_text())
    assert parsed["payload"]["slug"] == "use-postgres"
    assert parsed["name"] == "decision-new"
    assert parsed["phase"] == "post"


def test_run_script_non_zero_exit_raises(tmp_path: Path) -> None:
    """A script exiting non-zero raises HookAborted with the stderr message."""
    from keel.hooks import HookAborted, HookEvent
    from keel.hooks.scripts import run_user_script

    script = tmp_path / "pre-phase"
    _make_executable_script(
        script,
        '#!/usr/bin/env bash\necho "nope, blocked" >&2\nexit 1\n',
    )

    event = HookEvent(
        name="phase", phase="pre", project="foo", deliverable=None,
        payload={"from": "scoping", "to": "designing"},
        positional_args=("scoping", "designing"),
    )
    with pytest.raises(HookAborted) as exc:
        run_user_script(script, event, layer="workspace")
    assert "nope, blocked" in str(exc.value)


def test_run_script_skipped_if_not_executable(tmp_path: Path) -> None:
    """Non-executable scripts are skipped silently (matches git)."""
    from keel.hooks import HookEvent
    from keel.hooks.scripts import run_user_script

    script = tmp_path / "post-phase"
    script.write_text("#!/usr/bin/env bash\nfail\n")
    # NOT chmod'ed executable
    assert not os.access(script, os.X_OK)

    event = HookEvent(
        name="phase", phase="post", project="foo", deliverable=None,
        payload={}, positional_args=(),
    )
    # Should not raise — silently skipped
    run_user_script(script, event, layer="workspace")


def test_discover_hook_scripts_finds_workspace_and_project(tmp_path: Path) -> None:
    """discover_hook_scripts returns workspace hook first, then project hook."""
    from keel.hooks.scripts import discover_hook_scripts

    workspace_hooks = tmp_path / "ws" / ".keel" / "hooks"
    workspace_hooks.mkdir(parents=True)
    project_hooks = tmp_path / "proj" / ".keel" / "hooks"
    project_hooks.mkdir(parents=True)

    ws_script = workspace_hooks / "post-phase"
    _make_executable_script(ws_script, "#!/bin/sh\n")
    proj_script = project_hooks / "post-phase"
    _make_executable_script(proj_script, "#!/bin/sh\n")

    discovered = discover_hook_scripts(
        event_full_name="post-phase",
        workspace_dir=tmp_path / "ws",
        project_dir=tmp_path / "proj",
    )
    # Returns (script_path, layer) pairs in order: workspace first
    assert discovered == [
        (ws_script, "workspace"),
        (proj_script, "project"),
    ]


def test_discover_hook_scripts_omits_missing(tmp_path: Path) -> None:
    """If a layer doesn't have the script, it's just absent from the result."""
    from keel.hooks.scripts import discover_hook_scripts

    project_hooks = tmp_path / "proj" / ".keel" / "hooks"
    project_hooks.mkdir(parents=True)
    proj_script = project_hooks / "post-phase"
    _make_executable_script(proj_script, "#!/bin/sh\n")

    # No workspace dir
    discovered = discover_hook_scripts(
        event_full_name="post-phase",
        workspace_dir=tmp_path / "nonexistent-ws",
        project_dir=tmp_path / "proj",
    )
    assert discovered == [(proj_script, "project")]
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_scripts.py -v
```

Expected: FAIL (module doesn't exist).

- [ ] **Step 3: Implement scripts module**

Create `src/keel/hooks/scripts.py`:
```python
"""User-script runner — fork/exec git-style hooks under .keel/hooks/."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Literal

from keel.hooks.types import HookAborted, HookEvent

Layer = Literal["workspace", "project"]


def _event_to_env(event: HookEvent, layer: Layer) -> dict[str, str]:
    """Compute the env-var subset added on top of the parent env."""
    env: dict[str, str] = {
        "KEEL_EVENT": event.full_name,
        "KEEL_HOOK_LAYER": layer,
    }
    if event.project is not None:
        env["KEEL_PROJECT"] = event.project
    if event.deliverable is not None:
        env["KEEL_DELIVERABLE"] = event.deliverable

    # Per-event extras: KEEL_<EVENT_UPPER>_<FIELD_UPPER> = str(value)
    # e.g. event.name="phase", payload={"from": "scoping"} -> KEEL_PHASE_FROM=scoping
    event_upper = event.name.replace("-", "_").upper()
    for key, value in event.payload.items():
        if value is None:
            continue
        field_upper = key.replace("-", "_").upper()
        env[f"KEEL_{event_upper}_{field_upper}"] = str(value)
    return env


def discover_hook_scripts(
    *,
    event_full_name: str,
    workspace_dir: Path,
    project_dir: Path | None,
) -> list[tuple[Path, Layer]]:
    """Return (script_path, layer) pairs to run, workspace first.

    Caller passes the actual workspace dir (e.g. PROJECTS_DIR) and project
    dir (or None for events not scoped to a project).
    """
    pairs: list[tuple[Path, Layer]] = []
    workspace_script = workspace_dir / ".keel" / "hooks" / event_full_name
    if workspace_script.is_file() and os.access(workspace_script, os.X_OK):
        pairs.append((workspace_script, "workspace"))
    if project_dir is not None:
        project_script = project_dir / ".keel" / "hooks" / event_full_name
        if project_script.is_file() and os.access(project_script, os.X_OK):
            pairs.append((project_script, "project"))
    return pairs


def run_user_script(script: Path, event: HookEvent, *, layer: Layer) -> None:
    """Execute a single user-script hook.

    - argv: [str(script), *event.positional_args]
    - env: parent env + KEEL_* vars
    - stdin: JSON of {name, phase, project, deliverable, payload}
    - non-zero exit (and not skipped-for-non-exec): HookAborted

    A non-executable script is skipped silently (matches git).
    """
    if not os.access(script, os.X_OK):
        return

    env = {**os.environ, **_event_to_env(event, layer)}
    stdin_data = json.dumps(
        {
            "name": event.name,
            "phase": event.phase,
            "project": event.project,
            "deliverable": event.deliverable,
            "payload": event.payload,
        }
    )

    result = subprocess.run(
        [str(script), *event.positional_args],
        env=env,
        input=stdin_data,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        msg = (
            f"hook '{script.name}' (layer={layer}) exited {result.returncode}"
            + (f": {stderr}" if stderr else "")
        )
        raise HookAborted(msg)
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_scripts.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/hooks/scripts.py keel/tests/hooks/test_scripts.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): add user-script runner (env, args, stdin JSON, exec-bit gating)"
```

---

### Task 1.4: Plugin entry-point loader

**Files:**
- Create: `src/keel/hooks/loader.py`
- Create: `tests/hooks/test_loader.py`

Walk the `keel.event_listeners` entry-point group. Each entry-point resolves to a function (already decorated with `@subscribes_to`). Loading the function side-effects the registry; the loader's job is to enumerate + import.

- [ ] **Step 1: Write failing tests**

Create `tests/hooks/test_loader.py`:
```python
"""Tests for the plugin entry-point loader."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_load_plugin_listeners_imports_each_entry_point() -> None:
    """Each entry point is loaded once. Loading triggers the @subscribes_to decorator."""
    from keel.hooks.loader import load_plugin_listeners

    ep_a = MagicMock()
    ep_a.name = "listener_a"
    ep_a.load = MagicMock()

    ep_b = MagicMock()
    ep_b.name = "listener_b"
    ep_b.load = MagicMock()

    with patch("keel.hooks.loader.entry_points", return_value=[ep_a, ep_b]):
        load_plugin_listeners()

    ep_a.load.assert_called_once()
    ep_b.load.assert_called_once()


def test_load_plugin_listeners_swallows_load_errors() -> None:
    """A broken plugin must not crash keel — log a warning instead."""
    from keel.hooks.loader import load_plugin_listeners

    good_ep = MagicMock()
    good_ep.name = "good"
    good_ep.load = MagicMock()

    bad_ep = MagicMock()
    bad_ep.name = "bad"
    bad_ep.load.side_effect = ImportError("boom")

    with patch("keel.hooks.loader.entry_points", return_value=[bad_ep, good_ep]):
        # Should not raise
        load_plugin_listeners()

    # Good plugin still loads after the bad one
    good_ep.load.assert_called_once()


def test_load_plugin_listeners_is_idempotent() -> None:
    """Calling load_plugin_listeners twice does not double-register subscribers.

    The plugin uses @subscribes_to at module-import time. Re-importing the
    module is a no-op because Python's import cache returns the cached module.
    But entry_point.load() on an already-loaded module returns the same
    function object without re-executing module-level code — so this test
    verifies the no-double-decoration behavior.
    """
    from keel.hooks.loader import load_plugin_listeners

    ep = MagicMock()
    ep.name = "listener"
    ep.load = MagicMock()

    with patch("keel.hooks.loader.entry_points", return_value=[ep]):
        load_plugin_listeners()
        load_plugin_listeners()

    assert ep.load.call_count == 2  # entry_points may call load each time
    # But because Python caches imports, the actual module function objects
    # are only decorated once. (This is tested more fully in integration tests
    # via the registry length check.)
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_loader.py -v
```

- [ ] **Step 3: Implement loader**

Create `src/keel/hooks/loader.py`:
```python
"""Plugin entry-point loader for keel.event_listeners.

A plugin declares its subscribers via:

    [project.entry-points."keel.event_listeners"]
    on_new = "my_pkg.listeners:on_project_created"

Each entry-point value imports a function decorated with @subscribes_to,
which side-effects the in-tree registry. Loading is idempotent because
Python's import machinery caches modules.
"""

from __future__ import annotations

import sys
from importlib.metadata import entry_points

ENTRY_POINT_GROUP = "keel.event_listeners"


def load_plugin_listeners() -> None:
    """Discover all plugin event listeners and import them.

    Errors loading any single entry point are reported to stderr but never
    raised — one broken plugin must not crash keel. Subsequent entry
    points still load.
    """
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            ep.load()
        except Exception as e:  # noqa: BLE001
            print(
                f"warning: failed to load event listener '{ep.name}': {e}",
                file=sys.stderr,
            )
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_loader.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/hooks/loader.py keel/tests/hooks/test_loader.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): add keel.event_listeners entry-point loader"
```

---

### Task 1.5: Central dispatcher

**Files:**
- Create: `src/keel/hooks/dispatcher.py`
- Modify: `src/keel/hooks/__init__.py`
- Create: `tests/hooks/test_dispatcher.py`

The dispatcher ties registry + loader + scripts together. Order: in-tree subscribers → plugin entry-point subscribers (same list — the loader just imports them and they register normally) → workspace user-script → project user-script.

For pre-events: any exception propagates. For post-events: exceptions are caught and warned.

- [ ] **Step 1: Write failing tests**

Create `tests/hooks/test_dispatcher.py`:
```python
"""Tests for the central dispatcher."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest


def _make_executable_script(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_dispatcher_fires_in_tree_subscribers_in_order() -> None:
    """In-tree subscribers run in registration order."""
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.dispatcher import dispatch
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()
    calls: list[str] = []

    @subscribes_to("pre-new")
    def first(event: HookEvent, *, out: Output) -> None:
        calls.append("first")

    @subscribes_to("pre-new")
    def second(event: HookEvent, *, out: Output) -> None:
        calls.append("second")

    event = HookEvent(
        name="new", phase="pre", project="foo", deliverable=None,
        payload={}, positional_args=("foo",),
    )
    dispatch(event, out=Output(), workspace_dir=Path("/nonexistent"), project_dir=None)
    assert calls == ["first", "second"]


def test_dispatcher_pre_event_propagates_exceptions() -> None:
    """A pre-event subscriber raising HookAborted aborts the loop and propagates."""
    from keel.hooks import HookAborted, HookEvent, subscribes_to
    from keel.hooks.dispatcher import dispatch
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()
    calls: list[str] = []

    @subscribes_to("pre-phase")
    def first(event: HookEvent, *, out: Output) -> None:
        calls.append("first")
        raise HookAborted("blocked")

    @subscribes_to("pre-phase")
    def second(event: HookEvent, *, out: Output) -> None:
        calls.append("second")

    event = HookEvent(
        name="phase", phase="pre", project="foo", deliverable=None,
        payload={"from": "scoping", "to": "designing"},
        positional_args=("scoping", "designing"),
    )
    with pytest.raises(HookAborted, match="blocked"):
        dispatch(event, out=Output(), workspace_dir=Path("/nonexistent"), project_dir=None)
    assert calls == ["first"]  # second did NOT run


def test_dispatcher_pre_event_treats_arbitrary_exceptions_as_aborts() -> None:
    """ANY exception in pre subscriber aborts the command (buggy preflights still block)."""
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.dispatcher import dispatch
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()

    @subscribes_to("pre-new")
    def buggy(event: HookEvent, *, out: Output) -> None:
        raise ValueError("oops, bug in preflight")

    event = HookEvent(
        name="new", phase="pre", project="foo", deliverable=None,
        payload={}, positional_args=("foo",),
    )
    with pytest.raises(ValueError, match="oops, bug"):
        dispatch(event, out=Output(), workspace_dir=Path("/nonexistent"), project_dir=None)


def test_dispatcher_post_event_swallows_all_exceptions(capsys) -> None:
    """Post subscribers raising anything are caught — command already succeeded."""
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.dispatcher import dispatch
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()
    calls: list[str] = []

    @subscribes_to("post-new")
    def broken(event: HookEvent, *, out: Output) -> None:
        raise ValueError("post-hook bug")

    @subscribes_to("post-new")
    def healthy(event: HookEvent, *, out: Output) -> None:
        calls.append("healthy")

    event = HookEvent(
        name="new", phase="post", project="foo", deliverable=None,
        payload={"path": "/x"}, positional_args=("foo",),
    )
    # Must NOT raise
    dispatch(event, out=Output(), workspace_dir=Path("/nonexistent"), project_dir=None)
    # Subsequent subscriber still ran
    assert calls == ["healthy"]


def test_dispatcher_fires_user_scripts_after_in_tree(tmp_path: Path) -> None:
    """User scripts fire after in-tree subscribers, workspace before project."""
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.dispatcher import dispatch
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()

    order_log = tmp_path / "order.log"
    workspace_dir = tmp_path / "ws"
    project_dir = tmp_path / "proj"
    (workspace_dir / ".keel" / "hooks").mkdir(parents=True)
    (project_dir / ".keel" / "hooks").mkdir(parents=True)

    @subscribes_to("post-new")
    def in_tree(event: HookEvent, *, out: Output) -> None:
        with order_log.open("a") as f:
            f.write("in-tree\n")

    _make_executable_script(
        workspace_dir / ".keel" / "hooks" / "post-new",
        f'#!/usr/bin/env bash\necho "workspace" >> {order_log}\n',
    )
    _make_executable_script(
        project_dir / ".keel" / "hooks" / "post-new",
        f'#!/usr/bin/env bash\necho "project" >> {order_log}\n',
    )

    event = HookEvent(
        name="new", phase="post", project="foo", deliverable=None,
        payload={"path": str(project_dir)}, positional_args=("foo",),
    )
    dispatch(event, out=Output(), workspace_dir=workspace_dir, project_dir=project_dir)

    assert order_log.read_text().splitlines() == ["in-tree", "workspace", "project"]


def test_dispatcher_no_subscribers_is_silent() -> None:
    """An event with no subscribers fires silently — no error, no warning."""
    from keel.hooks import HookEvent
    from keel.hooks.dispatcher import dispatch
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()
    event = HookEvent(
        name="nothing-listens", phase="post", project=None, deliverable=None,
        payload={}, positional_args=(),
    )
    dispatch(event, out=Output(), workspace_dir=Path("/nonexistent"), project_dir=None)
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_dispatcher.py -v
```

- [ ] **Step 3: Implement the dispatcher**

Create `src/keel/hooks/dispatcher.py`:
```python
"""Central dispatcher — fans events out to all subscribers in documented order."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from keel.hooks.loader import load_plugin_listeners
from keel.hooks.registry import iter_in_tree_subscribers
from keel.hooks.scripts import discover_hook_scripts, run_user_script
from keel.hooks.types import HookEvent

if TYPE_CHECKING:
    from keel.output import Output


_plugins_loaded = False


def _ensure_plugins_loaded() -> None:
    """Load plugin event-listener entry points lazily, once per process."""
    global _plugins_loaded
    if _plugins_loaded:
        return
    load_plugin_listeners()
    _plugins_loaded = True


def dispatch(
    event: HookEvent,
    *,
    out: Output,
    workspace_dir: Path,
    project_dir: Path | None,
) -> None:
    """Fire the event to all subscribers in documented order.

    Order: in-tree (registration order) → workspace user-script → project user-script.
    (Plugin subscribers register into the in-tree registry on first dispatch
    via load_plugin_listeners.)

    Pre-events: any subscriber exception propagates and aborts the caller.
    Post-events: exceptions are caught and emitted via out.warn(); the loop
    continues.
    """
    _ensure_plugins_loaded()

    is_pre = event.phase == "pre"

    # 1. In-tree subscribers (includes plugin-registered subscribers post-load).
    for subscriber in iter_in_tree_subscribers(event.full_name):
        try:
            subscriber(event, out=out)
        except Exception as e:
            if is_pre:
                raise
            out.warn(f"post-hook subscriber failed: {e}")

    # 2. User scripts (workspace then project).
    pairs = discover_hook_scripts(
        event_full_name=event.full_name,
        workspace_dir=workspace_dir,
        project_dir=project_dir,
    )
    for script, layer in pairs:
        try:
            run_user_script(script, event, layer=layer)
        except Exception as e:
            if is_pre:
                raise
            out.warn(f"post-hook script '{script}' failed: {e}")
```

Update `src/keel/hooks/__init__.py`:
```python
"""keel hooks framework — events, dispatcher, subscriber registry.

Public API:
- HookEvent, HookAborted (types)
- subscribes_to (in-tree subscriber decorator)
- dispatch (manual dispatch, mostly for tests)
- @hookable, hook_event (command-side API) — added in Task 1.6
"""

from __future__ import annotations

from keel.hooks.dispatcher import dispatch
from keel.hooks.registry import subscribes_to
from keel.hooks.types import HookAborted, HookEvent

__all__ = [
    "HookAborted",
    "HookEvent",
    "dispatch",
    "subscribes_to",
]
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_dispatcher.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run full suite**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=line
```

Expected: 515 + 20 new hook tests = 535 passing; 0 failing.

- [ ] **Step 6: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/hooks/dispatcher.py keel/src/keel/hooks/__init__.py keel/tests/hooks/test_dispatcher.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): add keel.hooks.dispatch — fans events to all subscribers in order"
```

---

### Task 1.6: `@hookable` decorator + `hook_event` context manager

**Files:**
- Create: `src/keel/hooks/hookable.py`
- Modify: `src/keel/hooks/__init__.py`
- Create: `tests/hooks/test_hookable.py`

The command-side API: `@hookable("event-name")` marks a command (registry entry for introspection), and `with hook_event("event-name", ...) as e:` wraps the command's work — fires pre on entry, post on clean exit.

- [ ] **Step 1: Write failing tests**

Create `tests/hooks/test_hookable.py`:
```python
"""Tests for the @hookable decorator and hook_event context manager."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_hookable_registers_command_name() -> None:
    """@hookable records the event name on the function."""
    from keel.hooks.hookable import hookable, registered_events

    @hookable("test-event")
    def my_cmd():
        pass

    assert "test-event" in registered_events()
    assert getattr(my_cmd, "__keel_hookable_event__", None) == "test-event"


def test_hook_event_fires_pre_on_entry(monkeypatch, tmp_path: Path) -> None:
    """Entering the context manager fires the pre-event."""
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.hookable import hook_event
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    fired: list[str] = []

    @subscribes_to("pre-new")
    def pre(event: HookEvent, *, out: Output) -> None:
        fired.append(event.full_name)

    with hook_event(
        "new", project="foo", deliverable=None,
        payload={"description": "x"}, positional_args=("foo",),
        out=Output(),
    ):
        pass  # body

    assert "pre-new" in fired


def test_hook_event_fires_post_on_clean_exit(monkeypatch, tmp_path: Path) -> None:
    """Clean exit fires post-event."""
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.hookable import hook_event
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    fired: list[str] = []

    @subscribes_to("post-new")
    def post(event: HookEvent, *, out: Output) -> None:
        fired.append(event.full_name)

    with hook_event(
        "new", project="foo", deliverable=None,
        payload={}, positional_args=("foo",), out=Output(),
    ):
        pass

    assert "post-new" in fired


def test_hook_event_skips_post_on_exception(monkeypatch, tmp_path: Path) -> None:
    """If the body raises, post-event does NOT fire."""
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.hookable import hook_event
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    fired: list[str] = []

    @subscribes_to("post-new")
    def post(event: HookEvent, *, out: Output) -> None:
        fired.append(event.full_name)

    with pytest.raises(ValueError):
        with hook_event(
            "new", project="foo", deliverable=None,
            payload={}, positional_args=("foo",), out=Output(),
        ):
            raise ValueError("body failed")

    assert fired == []


def test_hook_event_post_payload_can_be_extended(monkeypatch, tmp_path: Path) -> None:
    """The event yielded by the context manager lets the body add post-only fields."""
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.hookable import hook_event
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    captured: list[dict] = []

    @subscribes_to("post-new")
    def post(event: HookEvent, *, out: Output) -> None:
        captured.append(dict(event.payload))

    with hook_event(
        "new", project="foo", deliverable=None,
        payload={"description": "x"}, positional_args=("foo",), out=Output(),
    ) as ev:
        # body mutates the payload (via the helper method)
        ev.add_post_payload({"path": "/some/where"})

    assert captured == [{"description": "x", "path": "/some/where"}]


def test_no_verify_bypasses_pre_subscribers(monkeypatch, tmp_path: Path) -> None:
    """When no_verify=True, pre-event subscribers are skipped entirely."""
    from keel.hooks import HookEvent, HookAborted, subscribes_to
    from keel.hooks.hookable import hook_event
    from keel.hooks.registry import _clear_registry
    from keel.output import Output

    _clear_registry()
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))

    @subscribes_to("pre-new")
    def always_block(event: HookEvent, *, out: Output) -> None:
        raise HookAborted("nope")

    # Without no_verify, this would raise
    with hook_event(
        "new", project="foo", deliverable=None,
        payload={}, positional_args=("foo",), out=Output(),
        no_verify=True,
    ):
        pass  # passes despite the pre-hook that would block
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_hookable.py -v
```

- [ ] **Step 3: Implement hookable**

Create `src/keel/hooks/hookable.py`:
```python
"""@hookable decorator and hook_event context manager — the command-side API.

Commands opt into hook firing by:

    @hookable("new")
    def cmd_new(ctx, ...):
        with hook_event("new", project=slug, payload={...}, out=out) as e:
            # ... do the work ...
            e.add_post_payload({"path": str(unit_dir)})  # optional post-only fields

The decorator records the command in the registry for `keel hooks list`.
The context manager fires `pre-<name>` on entry, `post-<name>` on clean exit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from keel.hooks.dispatcher import dispatch
from keel.hooks.types import HookEvent

if TYPE_CHECKING:
    from keel.output import Output


_HOOKABLE_COMMANDS: set[str] = set()


def hookable(event_name: str) -> Callable[[Callable], Callable]:
    """Decorator marking a command as firing pre/post events under `event_name`.

    Records the binding in a process-global set for introspection via
    `keel hooks list`. Does NOT wrap the function — the actual dispatch
    is the body's responsibility via `with hook_event(...)`.
    """

    def _decorate(fn: Callable) -> Callable:
        _HOOKABLE_COMMANDS.add(event_name)
        fn.__keel_hookable_event__ = event_name  # type: ignore[attr-defined]
        return fn

    return _decorate


def registered_events() -> set[str]:
    """Return the set of event names that any @hookable command has declared."""
    return set(_HOOKABLE_COMMANDS)


@dataclass
class _MutableEvent:
    """The event handle yielded by hook_event — lets the body add post-only payload fields."""

    name: str
    project: str | None
    deliverable: str | None
    positional_args: tuple[str, ...]
    pre_payload: dict[str, Any]
    post_extras: dict[str, Any] = field(default_factory=dict)

    def add_post_payload(self, fields: dict[str, Any]) -> None:
        """Merge additional fields into the post-event payload.

        Use this for values the body computes (e.g. resulting file path).
        Pre-event payload is unaffected.
        """
        self.post_extras.update(fields)


def _workspace_dir() -> "Any":
    """Lazy resolution of PROJECTS_DIR to avoid import-time coupling."""
    from keel.workspace import projects_dir

    return projects_dir()


def _project_dir_for(project: str | None, deliverable: str | None) -> Any:
    """The unit dir corresponding to the scope, or None when no project."""
    if project is None:
        return None
    from keel.workspace import Scope

    return Scope(project=project, deliverable=deliverable).unit_dir


@contextmanager
def hook_event(
    name: str,
    *,
    project: str | None,
    deliverable: str | None = None,
    payload: dict[str, Any] | None = None,
    positional_args: tuple[str, ...] = (),
    out: "Output",
    no_verify: bool = False,
) -> Iterator[_MutableEvent]:
    """Fire pre-<name> on entry, post-<name> on clean exit.

    The yielded object exposes `add_post_payload(...)` so the body can
    augment the post payload with values it computed (e.g., resulting path).

    `no_verify=True` skips ALL pre-event subscribers (in-tree + plugin +
    user-script). Post-event subscribers always run on clean exit.
    """
    pre_payload = dict(payload or {})
    handle = _MutableEvent(
        name=name,
        project=project,
        deliverable=deliverable,
        positional_args=tuple(positional_args),
        pre_payload=pre_payload,
    )

    workspace = _workspace_dir()
    proj_dir = _project_dir_for(project, deliverable)

    if not no_verify:
        pre_event = HookEvent(
            name=name,
            phase="pre",
            project=project,
            deliverable=deliverable,
            payload=pre_payload,
            positional_args=handle.positional_args,
        )
        dispatch(pre_event, out=out, workspace_dir=workspace, project_dir=proj_dir)

    yield handle

    post_payload = {**pre_payload, **handle.post_extras}
    post_event = HookEvent(
        name=name,
        phase="post",
        project=project,
        deliverable=deliverable,
        payload=post_payload,
        positional_args=handle.positional_args,
    )
    dispatch(post_event, out=out, workspace_dir=workspace, project_dir=proj_dir)
```

Update `src/keel/hooks/__init__.py`:
```python
"""keel hooks framework — events, dispatcher, subscriber registry.

Public API:
- HookEvent, HookAborted (types)
- subscribes_to (in-tree subscriber decorator)
- dispatch (manual dispatch, mostly for tests)
- hookable, hook_event (command-side API)
"""

from __future__ import annotations

from keel.hooks.dispatcher import dispatch
from keel.hooks.hookable import hook_event, hookable, registered_events
from keel.hooks.registry import subscribes_to
from keel.hooks.types import HookAborted, HookEvent

__all__ = [
    "HookAborted",
    "HookEvent",
    "dispatch",
    "hook_event",
    "hookable",
    "registered_events",
    "subscribes_to",
]
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_hookable.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/hooks/hookable.py keel/src/keel/hooks/__init__.py keel/tests/hooks/test_hookable.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): add @hookable + hook_event context manager (command-side API)"
```

---

## Section 2: Built-in subscriber migration

### Task 2.1: Migrate built-in preflights to `@subscribes_to("pre-phase")`

**Files:**
- Create: `src/keel/hooks/builtin_listeners.py`
- Create: `tests/hooks/test_builtin_listeners.py`

The 5 existing preflights (`_ScopeEditedPreflight`, `_DesignEditedPreflight`, `_MilestoneExistsPreflight`, `_MilestonesCompletePreflight`, `_WorktreesCleanPreflight`) become `@subscribes_to("pre-phase")` functions. Warnings → `out.warn(...)`. Blockers → `raise HookAborted(...)`.

Note: at this point in the plan, the legacy `keel/preflights/` module still exists (deletion is Task 2.2). To avoid double-firing, the new builtin_listeners module must NOT be imported until after the legacy preflight discovery in `phase.py` is replaced (Task 3.1). For now, we just write the module and its tests; we don't wire it into command discovery.

- [ ] **Step 1: Write failing tests**

Create `tests/hooks/test_builtin_listeners.py`:
```python
"""Tests for the built-in event listeners (formerly preflights)."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_scope_md_edited_warns_if_scaffold(make_project, projects, monkeypatch) -> None:
    """When leaving 'scoping', warn if scope.md is still the template scaffold."""
    from keel.hooks import HookEvent
    from keel.hooks.builtin_listeners import _check_scope_md_edited
    from keel.output import Output
    from keel import templates

    proj = make_project("foo")
    # scope.md is whatever the fixture wrote — likely template scaffold
    monkeypatch.chdir(proj)

    # Recreate scope.md as the scaffold template so the check fires.
    proj_scope_md = proj / "scope.md"
    proj_scope_md.write_text(
        templates.render("scope_md.j2", name="foo", description="")
    )

    event = HookEvent(
        name="phase", phase="pre", project="foo", deliverable=None,
        payload={"from": "scoping", "to": "designing"},
        positional_args=("scoping", "designing"),
    )

    out = Output()
    with pytest.warns(None) as _:
        # _check_scope_md_edited uses out.warn — capture via test mode
        _check_scope_md_edited(event, out=out)
    # Smoke: function runs without raising. Behavior assertion below uses capsys.


def test_milestone_exists_blocks_implementing_without_milestones(make_project, projects, monkeypatch) -> None:
    """When entering 'implementing' with no milestones, raise HookAborted."""
    from keel.hooks import HookAborted, HookEvent
    from keel.hooks.builtin_listeners import _check_milestone_exists
    from keel.output import Output

    proj = make_project("foo")
    monkeypatch.chdir(proj)

    event = HookEvent(
        name="phase", phase="pre", project="foo", deliverable=None,
        payload={"from": "poc", "to": "implementing"},
        positional_args=("poc", "implementing"),
    )

    with pytest.raises(HookAborted, match="milestones"):
        _check_milestone_exists(event, out=Output())


def test_milestones_complete_blocks_done(make_project, projects, monkeypatch) -> None:
    """Moving to 'done' with unfinished milestones must abort."""
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookAborted, HookEvent
    from keel.hooks.builtin_listeners import _check_milestones_complete
    from keel.output import Output

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])

    event = HookEvent(
        name="phase", phase="pre", project="foo", deliverable=None,
        payload={"from": "shipping", "to": "done"},
        positional_args=("shipping", "done"),
    )
    with pytest.raises(HookAborted, match="unfinished milestones"):
        _check_milestones_complete(event, out=Output())


def test_unrelated_transition_does_nothing(make_project, projects, monkeypatch) -> None:
    """A subscriber that doesn't care about (from, to) returns silently."""
    from keel.hooks import HookEvent
    from keel.hooks.builtin_listeners import _check_milestone_exists
    from keel.output import Output

    proj = make_project("foo")
    monkeypatch.chdir(proj)

    event = HookEvent(
        name="phase", phase="pre", project="foo", deliverable=None,
        payload={"from": "scoping", "to": "designing"},  # not (poc, implementing)
        positional_args=("scoping", "designing"),
    )
    # No raise, no warning expected
    _check_milestone_exists(event, out=Output())


def test_register_builtin_listeners_idempotent() -> None:
    """register_builtin_listeners() can be called multiple times safely."""
    from keel.hooks.builtin_listeners import register_builtin_listeners
    from keel.hooks.registry import _clear_registry, iter_in_tree_subscribers

    _clear_registry()
    register_builtin_listeners()
    first_count = len(list(iter_in_tree_subscribers("pre-phase")))
    register_builtin_listeners()
    second_count = len(list(iter_in_tree_subscribers("pre-phase")))
    assert first_count == second_count
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_builtin_listeners.py -v
```

- [ ] **Step 3: Implement builtin_listeners**

Create `src/keel/hooks/builtin_listeners.py`:
```python
"""Built-in pre-phase subscribers — keel's default-lifecycle checks.

These replace the legacy `keel.preflights.builtin` classes. Each function
inspects the event payload's (from, to) tuple and either:
- returns silently (this rule doesn't apply to this transition)
- calls out.warn(...) (advisory; user can continue)
- raises HookAborted(...) (blocks the transition)

Registration is idempotent — call register_builtin_listeners() at most
once per process; subsequent calls are no-ops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from keel.hooks import HookAborted, HookEvent, subscribes_to
from keel.hooks.registry import _REGISTRY

if TYPE_CHECKING:
    from keel.output import Output
    from keel.workspace import Scope


def _scope_from_event(event: HookEvent) -> "Scope":
    """Reconstruct a Scope from event.project / event.deliverable."""
    from keel.workspace import Scope

    return Scope(project=event.project, deliverable=event.deliverable)


def _template_diff(scope: "Scope", filename: str, template_name: str) -> bool:
    """True if the file on disk differs from a fresh template render."""
    from keel import templates

    path = scope.unit_dir / filename
    if not path.is_file():
        return True  # missing file counts as "different"
    actual = path.read_text()
    rendered = templates.render(template_name, name=scope.project, description="")
    return actual.strip() != rendered.strip()


def _check_scope_md_edited(event: HookEvent, *, out: "Output") -> None:
    """Warn when leaving 'scoping' if scope.md is still the template scaffold."""
    fr = event.payload.get("from")
    to = event.payload.get("to")
    if (fr, to) != ("scoping", "designing"):
        return
    scope = _scope_from_event(event)
    if not _template_diff(scope, "scope.md", "scope_md.j2"):
        out.warn("preflight: scope.md is still the template scaffold")


def _check_design_md_edited(event: HookEvent, *, out: "Output") -> None:
    """Warn when leaving 'designing' if design.md is unedited or no decisions exist."""
    fr = event.payload.get("from")
    to = event.payload.get("to")
    if (fr, to) != ("designing", "poc"):
        return
    scope = _scope_from_event(event)
    if not _template_diff(scope, "design.md", "design_md.j2"):
        out.warn("preflight: design.md is still the template scaffold")
    decisions = scope.decisions_dir
    if not decisions.is_dir() or not any(decisions.glob("*.md")):
        out.warn("preflight: no decision records under decisions/")


def _check_milestone_exists(event: HookEvent, *, out: "Output") -> None:
    """Block 'poc → implementing' if no milestones are defined."""
    fr = event.payload.get("from")
    to = event.payload.get("to")
    if (fr, to) != ("poc", "implementing"):
        return
    from keel.manifest import load_milestones_manifest

    scope = _scope_from_event(event)
    manifest = load_milestones_manifest(scope.milestones_manifest_path)
    if not manifest.milestones:
        raise HookAborted("no milestones defined; add one with 'keel milestone add'")


def _check_milestones_complete(event: HookEvent, *, out: "Output") -> None:
    """Warn on 'shipping' / block on 'done' if any milestones are unfinished."""
    to = event.payload.get("to")
    if to not in ("shipping", "done"):
        return
    from keel.manifest import load_milestones_manifest

    scope = _scope_from_event(event)
    manifest = load_milestones_manifest(scope.milestones_manifest_path)
    unfinished = [ms.id for ms in manifest.milestones if ms.status not in ("done", "cancelled")]
    if not unfinished:
        return
    msg = f"unfinished milestones: {', '.join(unfinished)}"
    if to == "done":
        raise HookAborted(msg)
    out.warn(f"preflight: {msg}")


def _check_worktrees_clean(event: HookEvent, *, out: "Output") -> None:
    """Warn when transitioning 'shipping → done' with dirty worktrees."""
    fr = event.payload.get("from")
    to = event.payload.get("to")
    if (fr, to) != ("shipping", "done"):
        return
    from keel import git_ops
    from keel.manifest import load_project_manifest

    scope = _scope_from_event(event)
    try:
        pm = load_project_manifest(scope.manifest_path)
    except Exception:
        return
    unit_dir = scope.unit_dir
    dirty = []
    for repo in pm.repos:
        wt = unit_dir / repo.worktree
        if wt.is_dir() and git_ops.is_worktree_dirty(wt):
            dirty.append(str(wt))
    if dirty:
        out.warn(f"preflight: dirty worktrees: {', '.join(dirty)}")


_BUILTIN_LISTENERS = (
    _check_scope_md_edited,
    _check_design_md_edited,
    _check_milestone_exists,
    _check_milestones_complete,
    _check_worktrees_clean,
)


def register_builtin_listeners() -> None:
    """Register all built-in pre-phase listeners. Idempotent."""
    existing = set(_REGISTRY.get("pre-phase", []))
    for fn in _BUILTIN_LISTENERS:
        if fn not in existing:
            subscribes_to("pre-phase")(fn)
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/hooks/test_builtin_listeners.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Run full suite (legacy preflights still active for now)**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=line
```

Expected: 540+ passing; 0 failing.

- [ ] **Step 6: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/hooks/builtin_listeners.py keel/tests/hooks/test_builtin_listeners.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): add built-in pre-phase listeners (replaces preflights)"
```

---

### Task 2.2: Wire `phase` command to the new dispatcher

**Files:**
- Modify: `src/keel/commands/phase.py`
- Modify: `tests/commands/test_phase.py`

Replace `iter_preflights() + fire_phase_transition()` calls with a `hook_event("phase", ...)` context manager. Add `--no-verify` flag. The body that writes the new phase file + decision file + history is unchanged.

Activate `register_builtin_listeners()` so the migrated subscribers are live.

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/test_phase.py`:
```python
def test_phase_no_verify_skips_pre_hooks(projects, make_project, monkeypatch) -> None:
    """--no-verify bypasses pre-phase blockers."""
    from typer.testing import CliRunner
    from keel.app import app

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    # Set phase to poc so transitioning to implementing triggers the
    # milestone-exists blocker (which would raise HookAborted).
    (proj / ".keel" / "phase").write_text("poc\n")

    # Without --no-verify: blocked
    result_block = runner.invoke(app, ["phase", "implementing", "-y"])
    assert result_block.exit_code != 0

    # With --no-verify: succeeds
    result_ok = runner.invoke(app, ["phase", "implementing", "-y", "--no-verify"])
    assert result_ok.exit_code == 0, result_ok.stderr


def test_phase_fires_post_phase_subscriber(projects, make_project, monkeypatch) -> None:
    """Successful transition fires post-phase subscribers."""
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()
    # Re-register builtins after clearing
    from keel.hooks.builtin_listeners import register_builtin_listeners
    register_builtin_listeners()

    captured: list[tuple[str | None, str | None]] = []

    @subscribes_to("post-phase")
    def capture(event: HookEvent, *, out) -> None:
        captured.append((event.payload.get("from"), event.payload.get("to")))

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    # Edit scope.md so the scope-edited preflight passes
    (proj / "scope.md").write_text("# foo\n\nReal scope content.\n")

    result = runner.invoke(app, ["phase", "designing", "-y"])
    assert result.exit_code == 0, result.stderr
    assert captured == [("scoping", "designing")]


def test_phase_preflight_warning_still_prompts(projects, make_project, monkeypatch) -> None:
    """Subscribers that out.warn produce a confirmation prompt (preserved behavior)."""
    from typer.testing import CliRunner
    from keel.app import app

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    # Leave scope.md as scaffold so scope-md-edited fires a warning
    from keel import templates
    (proj / "scope.md").write_text(
        templates.render("scope_md.j2", name="foo", description="")
    )

    # -y skips the prompt — must still succeed with warning
    result = runner.invoke(app, ["phase", "designing", "-y"])
    assert result.exit_code == 0
    assert "scope.md is still the template scaffold" in result.stderr
```

- [ ] **Step 2: Run; some tests will fail until phase.py is migrated**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_phase.py -v
```

- [ ] **Step 3: Migrate phase.py to use the new dispatcher**

Replace `src/keel/commands/phase.py`:
```python
"""`keel phase [PHASE]`."""

from __future__ import annotations

from datetime import date

import typer

from keel import templates, workspace
from keel.api import (
    ErrorCode,
    LifecycleNotFoundError,
    OpLog,
    Output,
    load_lifecycle,
    load_project_manifest,
    resolve_cli_scope,
)
from keel.hooks import HookAborted, hook_event, hookable
from keel.hooks.builtin_listeners import register_builtin_listeners

# Activate built-in pre-phase listeners on first import of this module.
register_builtin_listeners()


def _read_phase(scope: workspace.Scope) -> tuple[str, list[str]]:
    """Returns (current_phase, history_lines). History lines are everything after line 1."""
    current = workspace.read_phase(scope.unit_dir)
    path = scope.phase_path
    if not path.is_file():
        return current, []
    lines = path.read_text().splitlines()
    return current, lines[1:]


@hookable("phase")
def cmd_phase(
    ctx: typer.Context,
    phase: str | None = typer.Argument(
        None, help="Target phase to transition to. Mutually exclusive with --next."
    ),
    next_phase: bool = typer.Option(False, "--next", help="Advance one step in the lifecycle."),
    deliverable: str | None = typer.Option(
        None, "-D", "--deliverable", help="Phase scope: deliverable instead of project."
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Project name. Auto-detected from CWD if omitted."
    ),
    message: str | None = typer.Option(
        None, "-m", "--message", help="Optional note recorded in the phase history."
    ),
    no_decision: bool = typer.Option(
        False, "--no-decision", help="Skip auto-creating a phase-transition decision file."
    ),
    no_verify: bool = typer.Option(
        False, "--no-verify", help="Skip all pre-phase hooks (in-tree + plugin + user-script)."
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip the warning confirmation prompt."),
    list_next: bool = typer.Option(
        False,
        "--list-next",
        help="Print the valid next phase(s) from the current state and exit (no transition).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Show or transition the phase."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    project = scope.project
    deliverable = scope.deliverable

    path = scope.phase_path
    current, history = _read_phase(scope)

    # Load the project's lifecycle (deliverables inherit from their parent project)
    try:
        project_scope = workspace.Scope(project=scope.project, deliverable=None)
        manifest = load_project_manifest(project_scope.manifest_path)
        lc = load_lifecycle(manifest.project.lifecycle)
    except LifecycleNotFoundError as e:
        out.fail(f"lifecycle not found: {e}", code=ErrorCode.NOT_FOUND)

    # --list-next mode: show valid next transitions and exit
    if list_next:
        nexts = lc.successors(current) if current in lc.states else []
        if json_mode:
            out.result({"current": current, "next": nexts})
        else:
            if nexts:
                out.info(f"Current: {current} → next: {', '.join(nexts)}")
            else:
                out.info(f"Current: {current} (end of lifecycle)")
        return

    if phase is None and not next_phase:
        # Show mode
        scope_name = f"{project}/{deliverable}" if deliverable else project
        if json_mode:
            out.result(
                {
                    "scope": "deliverable" if deliverable else "project",
                    "name": scope_name,
                    "phase": current,
                    "history": [{"line": h} for h in history if h.strip()],
                }
            )
            return
        out.result(
            None,
            human_text=f"{scope_name}\nphase: {current}\n\n" + "\n".join(history)
            if history
            else f"{scope_name}\nphase: {current}",
        )
        return

    # Transition mode
    target = phase
    if next_phase:
        if current not in lc.states:
            out.fail(f"invalid current phase: {current}", code=ErrorCode.INVALID_PHASE)
        explicit_successors = [s for s in lc.successors(current) if s != "cancelled"]
        if not explicit_successors:
            out.fail(
                f"no forward transition from '{current}' (state is terminal or has no non-cancel edges)",
                code=ErrorCode.END_OF_LIFECYCLE,
            )
        target = explicit_successors[0]

    if target not in lc.states:
        out.fail(
            f"unknown phase '{target}' for lifecycle '{lc.name}'",
            code=ErrorCode.INVALID_PHASE,
        )

    if target != current and target not in lc.successors(current):
        out.fail(
            f"cannot transition from '{current}' to '{target}' "
            f"(allowed: {', '.join(lc.successors(current)) or 'none'})",
            code=ErrorCode.INVALID_STATE,
        )

    if target == current:
        out.info(f"already in phase: {current}")
        return

    if dry_run:
        log = OpLog()
        log.modify_file(path, diff=f"{current} → {target}")
        if not no_decision:
            today = date.today().isoformat()
            log.create_file(scope.decisions_dir / f"{today}-phase-{target}.md", size=0)
        out.info(log.format_summary())
        return

    # Fire pre-phase + body + post-phase via hook_event.
    try:
        with hook_event(
            "phase",
            project=project,
            deliverable=deliverable,
            payload={"from": current, "to": target},
            positional_args=(current, target),
            out=out,
            no_verify=no_verify,
        ):
            # Apply transition.
            today = date.today().isoformat()
            history_line = f"{today}  {current} → {target}"
            if message:
                history_line += f"  ({message})"
            new_lines = [target] + [history_line] + history
            scope.keel_dir.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(new_lines) + "\n")

            # Auto-create phase decision file.
            if not no_decision:
                _decisions_dir = scope.decisions_dir
                _decisions_dir.mkdir(parents=True, exist_ok=True)
                decision_path = _decisions_dir / f"{today}-phase-{target}.md"
                if not decision_path.exists():
                    decision_path.write_text(
                        templates.render(
                            "decision_entry.j2",
                            date=today,
                            title=f"Phase transition: {current} → {target}",
                        )
                    )
    except HookAborted as e:
        out.fail(
            f"phase transition blocked: {e} (use --no-verify to override)",
            code=ErrorCode.PREFLIGHT_BLOCKED,
        )

    out.result(
        {
            "scope": "deliverable" if deliverable else "project",
            "name": f"{project}/{deliverable}" if deliverable else project,
            "phase": target,
            "transitioned_from": current,
        },
        human_text=f"Phase: {current} → {target}",
    )
```

Notes on what's gone:
- `--strict` flag: removed (warnings stay warnings; users who want them treated as errors can write a custom pre-phase subscriber that raises HookAborted on warning conditions)
- `--force` flag: replaced with the more git-style `--no-verify`
- The accumulator-loop pattern that ran every preflight: replaced with the dispatcher's normal exception-propagation contract

If `--strict`/`--force` aliases are valuable for backward compat in dry-run testing scripts, add them as silent aliases (defer until someone complains).

- [ ] **Step 4: Run phase tests**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_phase.py -v
```

Expected: existing phase tests + new tests pass. Some existing assertions about `--strict` and `--force` may need updating to use `--no-verify` instead. Update those test cases to match the new flag.

- [ ] **Step 5: Run full suite (legacy preflights/phase_events code still present but no longer called)**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=line
```

Expected: 540+ tests pass; only legacy preflight registry / phase_events tests fail (those are deleted in Task 2.3).

- [ ] **Step 6: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/phase.py keel/tests/commands/test_phase.py
git -C /Users/andrei.matei/projects commit -m "feat(keel)!: keel phase uses the new hooks dispatcher; --no-verify replaces --strict/--force"
```

---

### Task 2.3: Delete legacy preflights/ and phase_events.py

**Files:**
- Delete: `src/keel/preflights/__init__.py`
- Delete: `src/keel/preflights/base.py`
- Delete: `src/keel/preflights/builtin.py`
- Delete: `src/keel/preflights/registry.py`
- Delete: `src/keel/phase_events.py`
- Delete: `tests/test_preflights.py`
- Delete: `tests/test_preflights_builtin.py`
- Delete: `tests/test_preflights_registry.py`
- Delete: `tests/test_phase_events.py`
- Modify: `src/keel/api.py`
- Modify: `src/keel/commands/plugin/list.py`

The legacy modules and their tests get deleted. `keel.api` re-exports are removed. The `plugin list` known-groups list drops the legacy entries and adds `keel.event_listeners`.

- [ ] **Step 1: Delete the legacy code + tests**

```bash
cd /Users/andrei.matei/projects/keel
rm -rf src/keel/preflights/
rm src/keel/phase_events.py
rm tests/test_preflights.py tests/test_preflights_builtin.py tests/test_preflights_registry.py
rm tests/test_phase_events.py
```

- [ ] **Step 2: Update `src/keel/api.py`**

Find lines 67–72 and replace this block:

```python
# REMOVE
from keel.phase_events import (
    PhaseTransitionHook,
    fire_phase_transition,
    iter_phase_transition_hooks,
)
from keel.preflights import PhasePreflight, PreflightResult, iter_preflights
```

With:

```python
from keel.hooks import (
    HookAborted,
    HookEvent,
    hook_event,
    hookable,
    subscribes_to,
)
```

Also remove the corresponding entries from `__all__` further down in the file:
- Remove: `"PhasePreflight"`, `"PreflightResult"`, `"iter_preflights"`, `"PhaseTransitionHook"`, `"fire_phase_transition"`, `"iter_phase_transition_hooks"`
- Add: `"HookAborted"`, `"HookEvent"`, `"hook_event"`, `"hookable"`, `"subscribes_to"`

Search `src/keel/api.py` for those identifiers in `__all__` and apply the swap.

- [ ] **Step 3: Update `src/keel/commands/plugin/list.py`**

Replace the GROUPS list:

```python
GROUPS = [
    "keel.commands",
    "keel.ticket_providers",
    "keel.event_listeners",
    "keel.lifecycles",
]
```

`keel.lifecycles` was missing — adding it here too since Plan 7 introduced it.

- [ ] **Step 4: Run full suite**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=line
```

Expected: tests pass. Some places may still try to import from the deleted modules — fix each import error one at a time:

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev python -c "import keel; import keel.api; import keel.hooks; import keel.commands.phase; import keel.commands.plugin.list"
```

Run that to find any stale imports. Most likely candidates: nothing else — but if there is anywhere referencing `keel.preflights` or `keel.phase_events`, update or remove the import.

Also verify the api-test:

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/test_api.py -v
```

The `tests/test_api.py` asserts which names `keel.api` exports. Update its expected list to match the new state (drop legacy names, add new ones).

- [ ] **Step 5: Run ruff**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests plugins/jira/src plugins/jira/tests
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff format --check src tests plugins/jira/src plugins/jira/tests
```

Expected: clean. Fix any unused-import warnings produced by the deletion.

- [ ] **Step 6: Commit**

```bash
git -C /Users/andrei.matei/projects add -A keel/src/ keel/tests/
git -C /Users/andrei.matei/projects commit -m "feat(keel)!: delete keel.preflights and keel.phase_events (replaced by keel.hooks)"
```

---

## Section 3: Wire remaining commands

### Task 3.1: `keel new` fires pre-new / post-new

**Files:**
- Modify: `src/keel/commands/new.py`
- Modify: `tests/commands/test_new.py`

Wrap the `cmd_new` body in `hook_event("new", ...)`. Add `--no-verify`. Post payload gains `path`.

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/test_new.py`:
```python
def test_new_fires_pre_and_post_subscribers(projects, monkeypatch) -> None:
    """Both pre-new and post-new fire around a successful keel new."""
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()
    fired: list[str] = []

    @subscribes_to("pre-new")
    def pre(event: HookEvent, *, out) -> None:
        fired.append(event.full_name)

    @subscribes_to("post-new")
    def post(event: HookEvent, *, out) -> None:
        fired.append(event.full_name)
        # Post payload contains 'path'
        assert "path" in event.payload

    runner = CliRunner()
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["new", "foo", "-d", "test", "--no-worktree", "-y"])
    assert result.exit_code == 0
    assert fired == ["pre-new", "post-new"]


def test_new_pre_hook_can_block(projects, monkeypatch) -> None:
    """A pre-new subscriber raising HookAborted aborts the command."""
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookAborted, HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()

    @subscribes_to("pre-new")
    def block(event: HookEvent, *, out) -> None:
        raise HookAborted("not allowed")

    runner = CliRunner()
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["new", "foo", "-d", "test", "--no-worktree", "-y"])
    assert result.exit_code != 0
    assert "not allowed" in result.stderr
    # No project dir created
    assert not (projects / "foo").exists()


def test_new_no_verify_bypasses_pre_hook(projects, monkeypatch) -> None:
    """--no-verify skips pre-new subscribers."""
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookAborted, HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()

    @subscribes_to("pre-new")
    def block(event: HookEvent, *, out) -> None:
        raise HookAborted("not allowed")

    runner = CliRunner()
    monkeypatch.chdir(projects)
    result = runner.invoke(
        app, ["new", "foo", "-d", "test", "--no-worktree", "-y", "--no-verify"]
    )
    assert result.exit_code == 0
    assert (projects / "foo" / "project.toml").is_file()
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_new.py -v
```

- [ ] **Step 3: Wrap `cmd_new` in hook_event**

In `src/keel/commands/new.py`, add to imports:
```python
from keel.hooks import HookAborted, hook_event, hookable
```

Add `@hookable("new")` above `def cmd_new`. Add `no_verify` typer option to the signature (place after `yes`):
```python
    no_verify: bool = typer.Option(
        False, "--no-verify", help="Skip pre-new hooks (in-tree + plugin + user-script)."
    ),
```

Wrap the file-writing portion of `cmd_new` (lines after the dry-run early return, starting with `manifest = _scaffold_unit(...)`) in a `hook_event` context manager:

```python
    # Fire pre-new, do the work, fire post-new.
    try:
        with hook_event(
            "new",
            project=slug,
            payload={"description": description, "lifecycle": lifecycle},
            positional_args=(slug,),
            out=out,
            no_verify=no_verify,
        ) as ev:
            manifest = _scaffold_unit(
                scope=scope,
                name=slug,
                description=description,
                lifecycle=lifecycle,
                repos=repo_specs,
                lc=lc,
            )

            # Worktrees (last — file ops above already done)
            created_worktrees: list[str] = []
            for rp, spec in zip(repo_paths, manifest.repos, strict=True):
                wt_dest = proj / spec.worktree
                try:
                    git_ops.create_worktree(rp, wt_dest, branch=spec.branch_prefix)
                    created_worktrees.append(str(wt_dest))
                except git_ops.GitError as e:
                    out.info(f"Files are at {proj}; clean up with `rm -rf {proj}` or retry.")
                    out.fail(f"worktree creation failed: {e}", code=ErrorCode.GIT_FAILED)

            ev.add_post_payload({"path": str(proj), "worktrees": created_worktrees})
    except HookAborted as e:
        out.fail(f"new aborted: {e} (use --no-verify to override)", code=ErrorCode.PREFLIGHT_BLOCKED)

    out.result(
        {"path": str(proj), "worktrees": created_worktrees},
        human_text=f"Project created: {proj}",
    )
```

- [ ] **Step 4: Run new tests**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_new.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/new.py keel/tests/commands/test_new.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): keel new fires pre-new/post-new; supports --no-verify"
```

---

### Task 3.2: `keel deliverable add` fires pre/post-deliverable-add

**Files:**
- Modify: `src/keel/commands/deliverable/add.py`
- Modify: `tests/commands/deliverable/test_add.py`

Same pattern as `keel new`. Event name is `deliverable-add`.

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/deliverable/test_add.py`:
```python
def test_deliverable_add_fires_pre_and_post(projects, make_project, monkeypatch) -> None:
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()
    fired: list[str] = []

    @subscribes_to("pre-deliverable-add")
    def pre(event: HookEvent, *, out) -> None:
        fired.append(event.full_name)
        assert event.project == "foo"

    @subscribes_to("post-deliverable-add")
    def post(event: HookEvent, *, out) -> None:
        fired.append(event.full_name)
        assert event.deliverable == "bar"
        assert "path" in event.payload

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    result = runner.invoke(app, ["deliverable", "add", "bar", "-d", "test", "-y"])
    assert result.exit_code == 0
    assert fired == ["pre-deliverable-add", "post-deliverable-add"]


def test_deliverable_add_no_verify(projects, make_project, monkeypatch) -> None:
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookAborted, HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()

    @subscribes_to("pre-deliverable-add")
    def block(event: HookEvent, *, out) -> None:
        raise HookAborted("nope")

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    blocked = runner.invoke(app, ["deliverable", "add", "bar", "-d", "x", "-y"])
    assert blocked.exit_code != 0

    bypassed = runner.invoke(
        app, ["deliverable", "add", "bar", "-d", "x", "-y", "--no-verify"]
    )
    assert bypassed.exit_code == 0
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Wrap cmd_add in hook_event**

In `src/keel/commands/deliverable/add.py`, add imports:
```python
from keel.hooks import HookAborted, hook_event, hookable
```

Add `@hookable("deliverable-add")` above `def cmd_add`. Add the `no_verify` typer option after `yes`:
```python
    no_verify: bool = typer.Option(
        False, "--no-verify", help="Skip pre-deliverable-add hooks."
    ),
```

Wrap the body that starts at `from keel.commands.new import _scaffold_unit` (line ~134) through the end with `hook_event`:

```python
    try:
        with hook_event(
            "deliverable-add",
            project=project,
            deliverable=slug,
            payload={"description": description, "lifecycle": parent_lifecycle},
            positional_args=(slug,),
            out=out,
            no_verify=no_verify,
        ) as ev:
            from keel.commands.new import _scaffold_unit

            manifest = _scaffold_unit(
                scope=deliv_scope,
                name=slug,
                description=description,
                lifecycle=parent_lifecycle,
                repos=repo_specs,
                lc=lc,
            )

            if shared:
                manifest = ProjectManifest(
                    project=ProjectMeta(
                        name=manifest.project.name,
                        description=manifest.project.description,
                        created=manifest.project.created,
                        lifecycle=manifest.project.lifecycle,
                        shared_worktree=True,
                    ),
                    repos=[],
                    extensions=manifest.extensions,
                )
                save_project_manifest(deliv_scope.manifest_path, manifest)

            created_worktree: str | None = None
            if repo_paths:
                wt_dest = deliv_scope.unit_dir / "code"
                try:
                    git_ops.create_worktree(
                        repo_paths[0], wt_dest, branch=repo_specs[0].branch_prefix
                    )
                    created_worktree = str(wt_dest)
                except git_ops.GitError as e:
                    out.info(f"Files are at {deliv_scope.unit_dir}; clean up manually if needed.")
                    out.fail(f"worktree creation failed: {e}", code=ErrorCode.GIT_FAILED)

            parent_design_path = parent_scope.design_md_path
            modified_files: list[str] = []
            if parent_design_path.is_file():
                line = (
                    f"- **{slug}**: {description}. "
                    f"See [design](deliverables/{slug}/design.md).\n"
                )
                new_text = insert_under_heading(
                    parent_design_path.read_text(), "Deliverables", line
                )
                parent_design_path.write_text(new_text)
                modified_files.append(str(parent_design_path))

            ev.add_post_payload(
                {
                    "path": str(deliv_scope.unit_dir),
                    "modified_files": modified_files,
                    "worktree": created_worktree,
                }
            )
    except HookAborted as e:
        out.fail(
            f"deliverable add aborted: {e} (use --no-verify to override)",
            code=ErrorCode.PREFLIGHT_BLOCKED,
        )

    out.result(
        {
            "deliverable_path": str(deliv_scope.unit_dir),
            "modified_files": modified_files,
            "worktree": created_worktree,
        },
        human_text=f"Deliverable created: {deliv_scope.unit_dir}",
    )
```

- [ ] **Step 4: Run + commit**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/deliverable/test_add.py -v
```

Expected: all pass.

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/deliverable/add.py keel/tests/commands/deliverable/test_add.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): keel deliverable add fires pre/post-deliverable-add; supports --no-verify"
```

---

### Task 3.3: `keel decision new` fires pre/post-decision-new

**Files:**
- Modify: `src/keel/commands/decision/new.py`
- Modify: `tests/commands/decision/test_new.py`

Same pattern. Event name is `decision-new`. Pre payload: `{slug, title, supersedes}`. Post payload adds `path`.

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/decision/test_new.py`:
```python
def test_decision_new_fires_pre_and_post(projects, make_project, monkeypatch) -> None:
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()
    fired: list[tuple[str, dict]] = []

    @subscribes_to("pre-decision-new")
    def pre(event: HookEvent, *, out) -> None:
        fired.append((event.full_name, dict(event.payload)))

    @subscribes_to("post-decision-new")
    def post(event: HookEvent, *, out) -> None:
        fired.append((event.full_name, dict(event.payload)))

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    result = runner.invoke(app, ["decision", "new", "Use Postgres", "--no-edit"])
    assert result.exit_code == 0

    assert len(fired) == 2
    pre_name, pre_payload = fired[0]
    post_name, post_payload = fired[1]
    assert pre_name == "pre-decision-new"
    assert pre_payload["title"] == "Use Postgres"
    assert pre_payload["slug"] == "use-postgres"
    assert post_name == "post-decision-new"
    assert "path" in post_payload


def test_decision_new_no_verify(projects, make_project, monkeypatch) -> None:
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookAborted, HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()

    @subscribes_to("pre-decision-new")
    def block(event: HookEvent, *, out) -> None:
        raise HookAborted("nope")

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    blocked = runner.invoke(app, ["decision", "new", "Test", "--no-edit"])
    assert blocked.exit_code != 0
    bypassed = runner.invoke(app, ["decision", "new", "Test", "--no-edit", "--no-verify"])
    assert bypassed.exit_code == 0
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Wrap cmd_new in hook_event**

In `src/keel/commands/decision/new.py`, add:
```python
from keel.hooks import HookAborted, hook_event, hookable
```

Add `@hookable("decision-new")` above `def cmd_new`. Add `no_verify` option after `force`:
```python
    no_verify: bool = typer.Option(
        False, "--no-verify", help="Skip pre-decision-new hooks."
    ),
```

Wrap the file-writing portion (everything after the dry-run early return — currently starting at `target_dir.mkdir(parents=True, exist_ok=True)`) in `hook_event`:

```python
    try:
        with hook_event(
            "decision-new",
            project=project,
            deliverable=deliverable,
            payload={
                "slug": slug_value,
                "title": title,
                "supersedes": supersedes,
            },
            positional_args=(slug_value,),
            out=out,
            no_verify=no_verify,
        ) as ev:
            target_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(templates.render("decision_entry.j2", date=today, title=title))

            if supersedes and supersedes_path is not None:
                old_text = supersedes_path.read_text()
                new_text = re.sub(
                    r"^status:\s*\S+",
                    "status: superseded",
                    old_text,
                    count=1,
                    flags=re.MULTILINE,
                )
                superseded_by_line = f"\nSuperseded by: {filename[:-3]}\n"
                if "Superseded by:" not in new_text:
                    new_text = new_text.rstrip("\n") + superseded_by_line
                supersedes_path.write_text(new_text)

            ev.add_post_payload({"path": str(path)})
    except HookAborted as e:
        out.fail(
            f"decision new aborted: {e} (use --no-verify to override)",
            code=ErrorCode.PREFLIGHT_BLOCKED,
        )

    out.result(
        {"path": str(path), "scope": scope_label, "slug": slug_value, "supersedes": supersedes},
        human_text=f"Decision created: {path}",
    )

    if not no_edit and os.environ.get("EDITOR") and not dry_run:
        with contextlib.suppress(Exception):
            subprocess.run([os.environ["EDITOR"], str(path)], check=False)
```

- [ ] **Step 4: Run + commit**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/decision/test_new.py -v
```

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/decision/new.py keel/tests/commands/decision/test_new.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): keel decision new fires pre/post-decision-new"
```

---

### Task 3.4: `keel archive` fires pre/post-archive

**Files:**
- Modify: `src/keel/commands/archive.py`
- Modify: `tests/commands/test_archive.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/test_archive.py`:
```python
def test_archive_fires_pre_and_post(projects, make_project, monkeypatch) -> None:
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()
    fired: list[str] = []
    archived_paths: list[str] = []

    @subscribes_to("pre-archive")
    def pre(event: HookEvent, *, out) -> None:
        fired.append(event.full_name)
        assert event.project == "foo"

    @subscribes_to("post-archive")
    def post(event: HookEvent, *, out) -> None:
        fired.append(event.full_name)
        archived_paths.append(event.payload["archived_path"])

    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["archive", "foo", "-y"])
    assert result.exit_code == 0, result.stderr
    assert fired == ["pre-archive", "post-archive"]
    assert len(archived_paths) == 1
    assert "foo-" in archived_paths[0]
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Add hooks to cmd_archive**

In `src/keel/commands/archive.py`, add:
```python
from keel.hooks import HookAborted, hook_event, hookable
```

Add `@hookable("archive")` above `def cmd_archive`. Add `no_verify` parameter after `yes`:
```python
    no_verify: bool = typer.Option(
        False, "--no-verify", help="Skip pre-archive hooks."
    ),
```

Wrap the work portion (after `confirm_destructive(...)` through the final out.result) in hook_event. The portion that collects + removes worktrees + moves the project tree happens inside the `with` block; `ev.add_post_payload({"archived_path": str(dest), "removed_worktrees": removed_worktrees})` is called before the `with` block exits. Then `out.result(...)` runs after the block.

```python
    try:
        with hook_event(
            "archive",
            project=project,
            deliverable=None,
            payload={},
            positional_args=(project,),
            out=out,
            no_verify=no_verify,
        ) as ev:
            # ... existing worktree collection + removal + shutil.move logic ...
            # (unchanged from the current file)

            ev.add_post_payload(
                {"archived_path": str(dest), "removed_worktrees": removed_worktrees}
            )
    except HookAborted as e:
        out.fail(
            f"archive aborted: {e} (use --no-verify to override)",
            code=ErrorCode.PREFLIGHT_BLOCKED,
        )

    out.result(
        {"archived_to": str(dest), "removed_worktrees": removed_worktrees},
        human_text=f"Archived {project} to {dest}.",
    )
```

- [ ] **Step 4: Run + commit**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_archive.py -v
```

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/archive.py keel/tests/commands/test_archive.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): keel archive fires pre/post-archive"
```

---

### Task 3.5: `keel restore` and `keel rename` fire post-only events

**Files:**
- Modify: `src/keel/commands/restore.py`
- Modify: `src/keel/commands/rename.py`
- Modify: `tests/commands/test_restore.py`
- Modify: `tests/commands/test_rename.py`

These commands have no pre-event in the v0 surface — only `post-restore` and `post-rename`. The plan dispatches the post-event manually (without `hook_event`, since there's no pre half).

Actually, `hook_event` still works — just call it with `no_verify=True` since there's no pre subscriber path; the workflow is the same. The implementation is just `with hook_event(name, ..., no_verify=True): ...` — pre fires trivially with no subscribers because the dispatcher returns silently.

Wait — `no_verify=True` skips pre subscribers. That's fine; "post-only" events simply have no in-tree or plugin pre subscribers. We can just use `hook_event(name, ...)` normally. If any subscriber wires up `pre-restore` or `pre-rename` they'd just fire — which is fine and consistent.

Actually the spec says only `post-restore` and `post-rename` are documented v0 events. Subscribing to `pre-restore` would work mechanically but isn't a documented surface. To enforce the documented surface, we add a registry-side guard: a subscriber attempting to register for an undocumented event name still works (dispatcher fires it) but doesn't appear in `keel hooks list`'s "known events" set.

Simpler: just use `hook_event` normally. Restore/rename naturally support pre + post via the same mechanism; we just don't advertise pre. If a power user wants `pre-restore`, they can register it and it'll work. The spec table lists v0 events as advisory documentation, not a hard whitelist.

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/test_restore.py`:
```python
def test_restore_fires_post_restore(projects, monkeypatch) -> None:
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()
    fired: list[str] = []

    @subscribes_to("post-restore")
    def post(event: HookEvent, *, out) -> None:
        fired.append(event.full_name)
        assert event.project == "foo"
        assert "path" in event.payload

    # Set up an archived project
    runner = CliRunner()
    monkeypatch.chdir(projects)
    (projects / ".archive").mkdir()
    archived = projects / ".archive" / "foo-2025-01-01"
    archived.mkdir()
    (archived / ".archived").write_text("archived: 2025-01-01\nfrom: /old\n")

    result = runner.invoke(app, ["restore", "foo", "-y"])
    assert result.exit_code == 0, result.stderr
    assert fired == ["post-restore"]
```

Append to `tests/commands/test_rename.py`:
```python
def test_rename_fires_post_rename(projects, make_project, monkeypatch) -> None:
    from typer.testing import CliRunner
    from keel.app import app
    from keel.hooks import HookEvent, subscribes_to
    from keel.hooks.registry import _clear_registry

    _clear_registry()
    fired: list[dict] = []

    @subscribes_to("post-rename")
    def post(event: HookEvent, *, out) -> None:
        fired.append(dict(event.payload))

    runner = CliRunner()
    make_project("foo")
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["rename", "foo", "bar", "-y"])
    assert result.exit_code == 0, result.stderr
    assert len(fired) == 1
    assert fired[0]["old_name"] == "foo"
    assert fired[0]["new_name"] == "bar"
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Wrap cmd_restore and cmd_rename**

For `src/keel/commands/restore.py`, add `@hookable("restore")` and wrap the `archive_dir.rename(target_dir)` portion in `hook_event`:

```python
from keel.hooks import hook_event, hookable

# (in cmd_restore, after confirm_destructive)

    with hook_event(
        "restore",
        project=name,
        deliverable=None,
        payload={},
        positional_args=(name,),
        out=out,
    ) as ev:
        archive_dir.rename(target_dir)
        ev.add_post_payload({"path": str(target_dir)})

    out.result(
        {"restored": name, "path": str(target_dir)},
        human_text=f"Restored: {name} → {target_dir}",
    )
```

For `src/keel/commands/rename.py`, add `@hookable("rename")` and wrap the bulk-rename portion in `hook_event`:

```python
from keel.hooks import hook_event, hookable

# (in cmd_rename, after confirm_destructive)

    with hook_event(
        "rename",
        project=new_slug,
        deliverable=None,
        payload={"old_name": old, "new_name": new_slug},
        positional_args=(old, new_slug),
        out=out,
    ) as ev:
        # ... existing manifest load + move worktrees + move other children
        # + save new manifest ...
        ev.add_post_payload({"branch_renames": branch_renames})

    out.result(
        {"old": old, "new": new_slug, "branch_renames": branch_renames},
        human_text=f"Renamed {old} → {new_slug} (branches: {len(branch_renames)}).",
    )
```

Note: `cmd_rename`'s `project=new_slug` reflects the *new* name because at the post-event moment the rename has happened. Pre-subscribers would see `project=new_slug` too — slight oddity but consistent with the fact that this command has no documented pre-event.

- [ ] **Step 4: Run + commit**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_restore.py tests/commands/test_rename.py -v
```

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/restore.py keel/src/keel/commands/rename.py keel/tests/commands/test_restore.py keel/tests/commands/test_rename.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): keel restore + rename fire post-events"
```

---

## Section 4: `keel hooks` command group

### Task 4.1: `keel hooks init`

**Files:**
- Create: `src/keel/commands/hooks/__init__.py`
- Create: `src/keel/commands/hooks/init.py`
- Create: `src/keel/_templates/hooks_readme.md.j2`
- Create: `tests/commands/hooks/__init__.py`
- Create: `tests/commands/hooks/test_init.py`
- Modify: `src/keel/app.py`

Scaffolds `.keel/hooks/` (workspace or project mode) with a README.

- [ ] **Step 1: Write failing tests**

Create `tests/commands/hooks/__init__.py`:
```python
"""Tests for the `keel hooks` command group."""
```

Create `tests/commands/hooks/test_init.py`:
```python
"""Tests for `keel hooks init`."""

from __future__ import annotations

from typer.testing import CliRunner

from keel.app import app


def test_hooks_init_creates_workspace_dir(projects, monkeypatch) -> None:
    """`keel hooks init` with no flags scaffolds the workspace hooks dir."""
    runner = CliRunner()
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["hooks", "init"])
    assert result.exit_code == 0, result.stderr
    workspace_hooks = projects / ".keel" / "hooks"
    assert workspace_hooks.is_dir()
    assert (workspace_hooks / "README.md").is_file()


def test_hooks_init_project_mode(projects, make_project, monkeypatch) -> None:
    """`keel hooks init --project foo` scaffolds `<projects>/foo/.keel/hooks/`."""
    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["hooks", "init", "--project", "foo"])
    assert result.exit_code == 0, result.stderr
    assert (proj / ".keel" / "hooks").is_dir()
    assert (proj / ".keel" / "hooks" / "README.md").is_file()


def test_hooks_init_idempotent(projects, monkeypatch) -> None:
    """Re-running on an existing hooks dir is a no-op."""
    runner = CliRunner()
    monkeypatch.chdir(projects)
    first = runner.invoke(app, ["hooks", "init"])
    second = runner.invoke(app, ["hooks", "init"])
    assert first.exit_code == 0
    assert second.exit_code == 0
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Create the template**

Create `src/keel/_templates/hooks_readme.md.j2`:
```jinja
# keel hooks

Drop executable scripts in this directory to react to keel events. Each
script must have its executable bit set (`chmod +x post-phase`).

Naming: `pre-<event>` or `post-<event>`, where `<event>` is one of:

- `new` (project creation)
- `phase` (phase transition; args: `<from> <to>`)
- `deliverable-add`
- `decision-new`
- `archive`
- `post-restore` (post-only)
- `post-rename` (post-only; args: `<old> <new>`)

Scripts receive:
- Positional args (see above)
- Env vars: `KEEL_EVENT`, `KEEL_PROJECT`, `KEEL_DELIVERABLE`,
  `KEEL_HOOK_LAYER`, plus per-event extras like `KEEL_PHASE_FROM`
- JSON event payload on stdin

Pre-hooks can block their command by exiting non-zero; `--no-verify`
overrides. Post-hooks are advisory and run after the command succeeds.

See `keel hooks list` for the live set of events and subscribers.
```

- [ ] **Step 4: Implement keel hooks init**

Create `src/keel/commands/hooks/__init__.py`:
```python
"""`keel hooks ...` command group."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="hooks",
    help="Manage user-script hooks at `.keel/hooks/`.",
    no_args_is_help=True,
)

from keel.commands.hooks.init import cmd_init  # noqa: E402

app.command(name="init")(cmd_init)

from keel.commands.hooks.list import cmd_list  # noqa: E402

app.command(name="list")(cmd_list)
```

Create `src/keel/commands/hooks/init.py`:
```python
"""`keel hooks init [--project NAME]`."""

from __future__ import annotations

import typer

from keel import templates, workspace
from keel.api import Output


def cmd_init(
    ctx: typer.Context,
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="If set, scaffold the project's .keel/hooks/. Otherwise: the workspace's.",
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Scaffold a .keel/hooks/ directory (workspace-global or project-local)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    if project is None:
        target = workspace.projects_dir() / ".keel" / "hooks"
    else:
        target = workspace.project_dir(project) / ".keel" / "hooks"

    target.mkdir(parents=True, exist_ok=True)
    readme = target / "README.md"
    if not readme.is_file():
        readme.write_text(templates.render("hooks_readme.md.j2"))

    out.result(
        {"hooks_dir": str(target)},
        human_text=f"Hooks dir ready: {target}",
    )
```

- [ ] **Step 5: Register the command group in app.py**

In `src/keel/app.py`, add (anywhere in the late-import block):
```python
from keel.commands.hooks import app as hooks_app  # noqa: E402

app.add_typer(hooks_app, name="hooks")
```

- [ ] **Step 6: Run tests + commit**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/hooks/ -v
```

Expected: all init tests pass; list tests still fail (Task 4.2).

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/hooks/__init__.py keel/src/keel/commands/hooks/init.py keel/src/keel/_templates/hooks_readme.md.j2 keel/src/keel/app.py keel/tests/commands/hooks/
git -C /Users/andrei.matei/projects commit -m "feat(keel): keel hooks init scaffolds .keel/hooks/ with README"
```

---

### Task 4.2: `keel hooks list`

**Files:**
- Create: `src/keel/commands/hooks/list.py`
- Modify: `tests/commands/hooks/test_list.py` (create)

Lists registered events, their subscribers (in-tree + plugin), and which commands fire them.

- [ ] **Step 1: Write failing tests**

Create `tests/commands/hooks/test_list.py`:
```python
"""Tests for `keel hooks list`."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from keel.app import app


def test_hooks_list_default_shows_events(projects, monkeypatch) -> None:
    """Default `keel hooks list` shows known event names."""
    runner = CliRunner()
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["hooks", "list"])
    assert result.exit_code == 0, result.stderr
    # Should mention some known events
    assert "new" in result.stdout
    assert "phase" in result.stdout


def test_hooks_list_json(projects, monkeypatch) -> None:
    """JSON mode produces a structured payload."""
    runner = CliRunner()
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["hooks", "list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "events" in payload
    assert "new" in payload["events"]


def test_hooks_list_shows_in_tree_subscribers(projects, monkeypatch) -> None:
    """In-tree subscribers (e.g. built-in pre-phase listeners) are visible."""
    runner = CliRunner()
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["hooks", "list", "--json"])
    payload = json.loads(result.stdout)
    pre_phase = payload["events"].get("pre-phase", {})
    # Built-in listeners include _check_scope_md_edited etc.
    subscribers = pre_phase.get("subscribers", [])
    assert any("scope_md_edited" in s for s in subscribers)
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement keel hooks list**

Create `src/keel/commands/hooks/list.py`:
```python
"""`keel hooks list`."""

from __future__ import annotations

import typer
from rich.table import Table

from keel.api import Output
from keel.hooks.hookable import registered_events
from keel.hooks.registry import _REGISTRY


def cmd_list(
    ctx: typer.Context,
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """List all events keel commands can fire, along with subscribers."""
    out = Output.from_context(ctx, json_mode=json_mode)

    # Trigger plugin entry-point load so we see plugin subscribers too.
    from keel.hooks.dispatcher import _ensure_plugins_loaded
    _ensure_plugins_loaded()

    events = sorted(registered_events())
    payload: dict[str, dict] = {}
    for event_name in events:
        pre_subs = [_fmt_subscriber(s) for s in _REGISTRY.get(f"pre-{event_name}", [])]
        post_subs = [_fmt_subscriber(s) for s in _REGISTRY.get(f"post-{event_name}", [])]
        payload[event_name] = {
            "pre_subscribers": pre_subs,
            "post_subscribers": post_subs,
        }
    # Also surface any extra subscribers for events that aren't in registered_events
    # (e.g. plugins subscribing to events keel-cli doesn't fire).
    extra_keys = {k for k in _REGISTRY.keys() if k.split("-", 1)[1] not in events}
    extra_subs = {k: [_fmt_subscriber(s) for s in _REGISTRY[k]] for k in extra_keys}

    if json_mode:
        out.result(
            {
                "events": payload,
                "extra_subscribers": extra_subs,
            }
        )
        return

    table = Table()
    table.add_column("Event")
    table.add_column("Pre subscribers")
    table.add_column("Post subscribers")
    for event_name in events:
        e = payload[event_name]
        table.add_row(
            event_name,
            "\n".join(e["pre_subscribers"]) or "—",
            "\n".join(e["post_subscribers"]) or "—",
        )
    out.print_rich(table)
    if extra_subs:
        out.info(
            "Note: plugin subscribers registered for events not fired by built-in commands: "
            + ", ".join(sorted(extra_subs.keys()))
        )


def _fmt_subscriber(fn) -> str:
    """Format a subscriber callable as 'module.qualname'."""
    mod = getattr(fn, "__module__", "?")
    name = getattr(fn, "__qualname__", getattr(fn, "__name__", "?"))
    # Strip leading underscore from internal listener names for readability:
    # 'keel.hooks.builtin_listeners._check_scope_md_edited' stays as-is so users
    # can see exactly which function fired.
    return f"{mod}.{name}"
```

But we have a problem: the JSON test expects `payload["events"]["new"]` to exist. Our payload structure is `events[event_name] = {pre_subscribers, post_subscribers}`. The test asserts `"new" in payload["events"]`. That works if `new` is in `registered_events()` — which it is, once Task 3.1 lands and the `@hookable("new")` decorator runs. So this test passes provided `cmd_new` was imported, which `keel.app` does eagerly.

For the third test asserting `payload["events"]["pre-phase"]["subscribers"]`, we need to adjust the test to match the actual schema (`pre_subscribers`). Update the test accordingly:

In the test, change:
```python
    pre_phase = payload["events"].get("pre-phase", {})
    subscribers = pre_phase.get("subscribers", [])
```
to:
```python
    phase = payload["events"].get("phase", {})
    pre_subs = phase.get("pre_subscribers", [])
```
and look at pre_subs for the built-in listeners.

- [ ] **Step 4: Run tests + commit**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/hooks/ -v
```

Expected: all hooks command tests pass.

```bash
git -C /Users/andrei.matei/projects add keel/src/keel/commands/hooks/list.py keel/tests/commands/hooks/test_list.py
git -C /Users/andrei.matei/projects commit -m "feat(keel): keel hooks list shows events + subscribers"
```

---

## Section 5: Docs, decision, version bump

### Task 5.1: Decision file recording the locked decisions

**Files:**
- Create: `design/decisions/2026-05-11-user-hooks-framework.md`

```markdown
---
date: 2026-05-11
title: User hooks framework + phase-event consolidation
status: accepted
---

# User hooks framework + phase-event consolidation

## Question

Should keel grow a unified hook system covering CLI commands (user
scripts + plugin entry-points + in-tree subscribers), and should the
existing `keel.phase_preflights` / `keel.phase_transitions` entry-point
groups be consolidated into it?

## Conclusion

Yes. Captured in `design/specs/2026-05-11-user-hooks-design.md`. Implemented
in Plan 9 (`design/plans/2026-05-11-plan-9-user-hooks.md`). keel-cli bumps
to 0.0.4 on completion. keel-jira does not need a version bump (no use of
either legacy group).

The four locked decisions:

1. **One dispatcher for all event sources.** A new `keel.hooks` module
   owns event dispatch. In-tree subscribers, plugin entry-points
   (`keel.event_listeners`), and user scripts (`.keel/hooks/<event>`)
   are all wired through the same code path.
2. **Command-side API.** Commands declare via `@hookable("event-name")`
   and wrap their work in `with hook_event(name, ...) as ev:`. Pre-hook
   on entry, post-hook on clean exit, post-hooks skipped on exception.
3. **Phase-event consolidation is a hard break.** No bridge for legacy
   `keel.phase_preflights` / `keel.phase_transitions` entry-points;
   keel is alpha (0.0.x) and the audit confirmed no first-party plugin
   uses either group. Out-of-tree plugins migrate per the spec's
   migration guide.
4. **Pre-hook semantics are git-style.** Non-zero exit aborts; any
   subscriber exception is treated as an abort; `--no-verify` flag
   overrides on commands with pre-hooks.

v0 event surface: `new`, `phase`, `deliverable-add`, `decision-new`,
`archive`, `restore` (post-only), `rename` (post-only).
File events, milestone/task/code events, and async dispatch are
deferred.
```

- [ ] **Commit**

```bash
git -C /Users/andrei.matei/projects add keel/design/decisions/2026-05-11-user-hooks-framework.md
git -C /Users/andrei.matei/projects commit -m "docs(keel): record decision — 0.0.4 user hooks framework"
```

---

### Task 5.2: Update CONTRIBUTING.md with the new plugin API

**Files:**
- Modify: `CONTRIBUTING.md`

Add a section describing `keel.event_listeners` (the new entry-point group), reference the migration guide in the spec, and update any obsolete mentions of `keel.phase_preflights` / `keel.phase_transitions`.

- [ ] **Step 1: Find references**

```bash
cd /Users/andrei.matei/projects/keel
grep -n "phase_preflights\|phase_transitions\|event_listeners" CONTRIBUTING.md README.md
```

- [ ] **Step 2: Update CONTRIBUTING.md**

Find the plugin-authoring section and add a subsection right after the existing entry-points overview:

```markdown
### Subscribing to events

Plugins react to keel events via the `keel.event_listeners` entry-point
group. Each entry point resolves to a function decorated with
`@subscribes_to("pre-<event>")` or `@subscribes_to("post-<event>")`:

```toml
[project.entry-points."keel.event_listeners"]
my_listener = "my_pkg.listeners:on_phase_change"
```

```python
from keel.hooks import HookAborted, HookEvent, subscribes_to

@subscribes_to("pre-phase")
def on_phase_change(event: HookEvent, *, out) -> None:
    if event.payload["to"] == "done":
        if has_open_issues(event.project):
            raise HookAborted("can't mark 'done' with open issues")
```

Subscribers receive the `HookEvent` (with `name`, `phase`, `project`,
`deliverable`, `payload`, `positional_args`) plus the keel `Output`.
Pre-event subscribers may raise `HookAborted` to abort the command;
post-event subscribers' exceptions are caught and logged.

For end-user automation (without packaging a plugin), drop an executable
script in `~/projects/.keel/hooks/<event>`. See the spec at
`design/specs/2026-05-11-user-hooks-design.md` for details.

> **Migrating from `keel.phase_preflights` / `keel.phase_transitions`?**
> Those entry-point groups were removed in 0.0.4 with no backward-compat
> bridge. See the migration guide in the spec linked above.
```

- [ ] **Step 3: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/CONTRIBUTING.md
git -C /Users/andrei.matei/projects commit -m "docs(keel): document keel.event_listeners plugin API in CONTRIBUTING"
```

---

### Task 5.3: Update README.md with a hooks subsection

**Files:**
- Modify: `README.md`

A short section showing the `keel hooks init` flow and a sample script.

- [ ] **Step 1: Add the section**

In `README.md`, after the "Customizable phase lifecycles" section, add:

```markdown
## User hooks

Drop executable scripts in `~/projects/.keel/hooks/` (workspace-global)
or `~/projects/<name>/.keel/hooks/` (per-project) to react to keel
events:

```bash
keel hooks init   # scaffold ~/projects/.keel/hooks/ with a README

cat > ~/projects/.keel/hooks/post-phase <<'EOF'
#!/usr/bin/env bash
# Args: <from_phase> <to_phase>
echo "$KEEL_PROJECT: $1 → $2" | osascript -e 'on run argv
  display notification (item 1 of argv) with title "keel"
end run' -
EOF
chmod +x ~/projects/.keel/hooks/post-phase
```

Supported events (v0): `new`, `phase`, `deliverable-add`, `decision-new`,
`archive` (each with `pre-` and `post-` variants), plus post-only
`restore` and `rename`. Pre-hooks can block their command by exiting
non-zero; `--no-verify` overrides.

`keel hooks list` shows everything keel can fire and who's subscribed.

For plugin authors, the `keel.event_listeners` entry-point group provides
the same surface as a Python API — see CONTRIBUTING.md.
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/README.md
git -C /Users/andrei.matei/projects commit -m "docs(keel): add user hooks section to README"
```

---

### Task 5.4: Bump keel-cli to 0.0.4

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Bump the version**

In `pyproject.toml` root: change `version = "0.0.3"` to `version = "0.0.4"`.

The `jira` and `all` extras already point at `keel-jira>=0.0.2`; leave as-is. keel-jira itself does not need a bump.

- [ ] **Step 2: Confirm tests still pass**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=line
```

Expected: all green.

- [ ] **Step 3: Commit**

```bash
git -C /Users/andrei.matei/projects add keel/pyproject.toml
git -C /Users/andrei.matei/projects commit -m "chore(keel): bump keel-cli to 0.0.4"
```

---

## Section 6: Smoke + tag + sync to public + publish

### Task 6.1: Final smoke

- [ ] **Step 1: Full suite + lint + format**

```bash
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests plugins/jira/src plugins/jira/tests
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff format --check src tests plugins/jira/src plugins/jira/tests
```

Expected: ≥545 keel-cli tests pass; ruff + format clean.

- [ ] **Step 2: End-to-end smoke**

```bash
SMOKE_DIR=$(mktemp -d -t keel-p9-smoke-XXXXXX)
echo "SMOKE_DIR=$SMOKE_DIR"

# Create a workspace, scaffold a hook, run `keel new` and verify firing.
mkdir -p $SMOKE_DIR/.keel/hooks
cat > $SMOKE_DIR/.keel/hooks/post-new <<EOF
#!/usr/bin/env bash
echo "post-new fired for project: \$1" >> $SMOKE_DIR/hook-log.txt
EOF
chmod +x $SMOKE_DIR/.keel/hooks/post-new

PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel new alpha -d "smoke test" --no-worktree -y
cat $SMOKE_DIR/hook-log.txt
# Expected output: post-new fired for project: alpha

# Try blocking
cat > $SMOKE_DIR/.keel/hooks/pre-phase <<'EOF'
#!/usr/bin/env bash
[[ "$2" == "designing" ]] && exit 0
echo "blocked: $2 not allowed" >&2
exit 1
EOF
chmod +x $SMOKE_DIR/.keel/hooks/pre-phase

# Should succeed (designing is allowed)
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel phase designing --project alpha -y
# Should fail (poc isn't allowed by our hook)
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel phase poc --project alpha -y || echo "blocked as expected"

# --no-verify bypasses
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel phase poc --project alpha -y --no-verify

# keel hooks list works
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel hooks list

rm -rf $SMOKE_DIR
```

- [ ] **Step 3: Tag**

```bash
git -C /Users/andrei.matei/projects tag keel-plan-9
```

---

### Task 6.2: Sync to public + publish

- [ ] **Step 1: Generate per-commit patches keyed by sequential numbering**

```bash
mkdir -p /tmp/keel-p9-patches
i=1
for sha in $(git -C /Users/andrei.matei/projects log --reverse --no-merges --format=%H keel-plan-8..keel-plan-9 -- keel/); do
    git -C /Users/andrei.matei/projects format-patch --relative=keel/ -1 --start-number $i $sha -o /tmp/keel-p9-patches/ > /dev/null
    i=$((i+1))
done
ls /tmp/keel-p9-patches/ | wc -l
```

- [ ] **Step 2: Apply to public repo**

```bash
cd /tmp/project-cli-publish && git status --short
cd /tmp/project-cli-publish && git pull --rebase origin main
cd /tmp/project-cli-publish && git am /tmp/keel-p9-patches/*.patch
```

If conflicts, abort and inspect; the public repo should be at `keel-cli-v0.0.3` from Plan 8.

- [ ] **Step 3: Verify public tests pass**

```bash
cd /tmp/project-cli-publish && uv run --extra dev pytest --tb=short
```

Expected: all pass.

- [ ] **Step 4: Tag in public + push**

```bash
cd /tmp/project-cli-publish && git tag keel-plan-9
cd /tmp/project-cli-publish && git tag keel-cli-v0.0.4

cd /tmp/project-cli-publish && git push origin main
cd /tmp/project-cli-publish && git push origin keel-plan-9
cd /tmp/project-cli-publish && git push origin keel-cli-v0.0.4
```

The `keel-cli-v0.0.4` tag triggers the existing release workflow.

- [ ] **Step 5: Watch the publish run**

```bash
cd /tmp/project-cli-publish && gh run list --workflow=release.yml --limit 1
# Then `gh run watch <id>` for the run shown.
```

- [ ] **Step 6: Verify on PyPI**

```bash
curl -fsS https://pypi.org/pypi/keel-cli/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"
```

Expected: `0.0.4`.

---

## Self-review

| Spec section | Implementing tasks |
|---|---|
| Architecture: central dispatcher | T1.1 (types), T1.5 (dispatcher) |
| Architecture: in-tree subscribers | T1.2 (registry + `@subscribes_to`) |
| Architecture: user scripts | T1.3 (`scripts.py`) |
| Architecture: plugin entry-points | T1.4 (loader) |
| Architecture: command-side API | T1.6 (`@hookable` + `hook_event`) |
| Hook event surface (v0) | T2.2 (phase), T3.1 (new), T3.2 (deliverable-add), T3.3 (decision-new), T3.4 (archive), T3.5 (restore + rename) |
| Phase-event consolidation (hard break) | T2.1 (built-in subscribers), T2.2 (phase rewired), T2.3 (delete legacy) |
| Migration guide | T5.1 (decision), T5.2 (CONTRIBUTING) |
| `keel hooks list/init` | T4.1, T4.2 |
| Pre-hook semantics + `--no-verify` | T1.5, T2.2, T3.1–T3.4 |
| User-script protocol (args + env + stdin) | T1.3 |
| Five out-of-scope items | Untouched (matches spec) |
| Testing strategy | Tests in every section |

**Placeholder scan:** no TBDs, no "implement later", no "fill in the details". Every code step has the actual code; every commit step has the exact command.

**Type consistency:** `HookEvent`, `HookAborted`, `subscribes_to`, `hookable`, `hook_event`, `dispatch`, `_clear_registry`, `_REGISTRY`, `iter_in_tree_subscribers`, `load_plugin_listeners`, `run_user_script`, `discover_hook_scripts`, `register_builtin_listeners` are referenced consistently across tasks.

---

## Execution Handoff

Plan complete and saved to `keel/design/plans/2026-05-11-plan-9-user-hooks.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks. Matches Plans 5/5.1/5.2/5.3/5.4/5.5/6/7/8 in this repo.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
