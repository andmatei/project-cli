# Plan 7: Customizable phase lifecycles (FSM) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded 6-phase lifecycle with a finite-state-machine model loaded from TOML files. Users define custom workflows in `~/projects/.keel/lifecycles/<name>.toml`; projects pick one at creation time via `keel new --lifecycle <name>`.

**Architecture:** New `keel.lifecycles` package contains Pydantic models (`Lifecycle`, `LifecycleState`), a loader with precedence (project → user library → built-ins → plugins), and shipped default TOML mirroring the current 6 phases. The existing `keel.lifecycle` module keeps its public signatures via a thin shim that delegates to `load_lifecycle("default")`. Phase commands use `Lifecycle.successors()` for transitions; `keel phase --list-next` returns FSM successors which can be multiple for branching workflows.

**Tech Stack:** Same as Plan 6. Reuses Pydantic, tomllib (read), tomlkit (write), typer.

---

## Pre-requisites

- Plan 6 complete; tag `keel-plan-6` exists.
- 442 tests pass on `main`.
- Ruff + ruff format clean.

---

## File Structure

After Plan 7 lands:

```
src/keel/
├── lifecycle.py                       # MODIFY — wrap default lifecycle for backward compat
├── lifecycles/                        # NEW — FSM machinery
│   ├── __init__.py                    # re-exports
│   ├── models.py                      # Lifecycle, LifecycleState (Pydantic)
│   ├── loader.py                      # load_lifecycle, iter_lifecycles, LifecycleNotFoundError
│   └── defaults/
│       ├── __init__.py                # package marker (so default.toml ships in the wheel)
│       └── default.toml               # current 6 phases as TOML
├── manifest/
│   └── models.py                      # MODIFY — add `lifecycle: str = "default"` to ProjectMeta
├── commands/
│   ├── new.py                         # MODIFY — accept --lifecycle, write to manifest
│   ├── phase.py                       # MODIFY — use Lifecycle FSM for transitions
│   └── lifecycle/                     # NEW — keel lifecycle ... subgroup
│       ├── __init__.py
│       ├── list.py
│       ├── show.py
│       ├── validate.py
│       └── init.py
├── api.py                             # MODIFY — export Lifecycle, LifecycleState, load_lifecycle, iter_lifecycles, LifecycleNotFoundError
├── app.py                             # MODIFY — register lifecycle subapp
└── _templates/
    └── lifecycle.toml.j2              # NEW — scaffold template for `keel lifecycle init`

tests/
├── lifecycles/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_loader.py
│   └── test_defaults.py
└── commands/
    └── lifecycle/
        ├── __init__.py
        ├── test_list.py
        ├── test_show.py
        ├── test_validate.py
        └── test_init.py
```

---

## Section 1: Lifecycle models

### Task 1.1: `Lifecycle` and `LifecycleState` Pydantic models

**Files:**
- Create: `src/keel/lifecycles/__init__.py`
- Create: `src/keel/lifecycles/models.py`
- Create: `tests/lifecycles/__init__.py` (empty marker)
- Create: `tests/lifecycles/test_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/lifecycles/__init__.py` (empty file).

Create `tests/lifecycles/test_models.py`:

```python
"""Tests for Lifecycle / LifecycleState Pydantic models."""

import pytest
from pydantic import ValidationError

from keel.lifecycles.models import Lifecycle, LifecycleState


def _minimal_lifecycle(**overrides):
    base = {
        "name": "test",
        "initial": "a",
        "terminal": ["c"],
        "states": {"a": {}, "b": {}, "c": {}},
        "transitions": {"a": ["b"], "b": ["c"]},
    }
    base.update(overrides)
    return Lifecycle.model_validate(base)


def test_lifecycle_state_defaults() -> None:
    s = LifecycleState()
    assert s.description == ""
    assert s.cancellable is True


def test_lifecycle_minimal_round_trip() -> None:
    lc = _minimal_lifecycle()
    assert lc.name == "test"
    assert lc.initial == "a"
    assert lc.terminal == ["c"]
    assert "a" in lc.states


def test_lifecycle_initial_must_be_in_states() -> None:
    with pytest.raises(ValidationError):
        _minimal_lifecycle(initial="ghost")


def test_lifecycle_terminal_must_be_in_states() -> None:
    with pytest.raises(ValidationError):
        _minimal_lifecycle(terminal=["ghost"])


def test_lifecycle_transitions_keys_must_be_in_states() -> None:
    with pytest.raises(ValidationError):
        _minimal_lifecycle(transitions={"ghost": ["c"]})


def test_lifecycle_transitions_values_must_be_in_states() -> None:
    with pytest.raises(ValidationError):
        _minimal_lifecycle(transitions={"a": ["ghost"]})


def test_lifecycle_successors_simple() -> None:
    lc = _minimal_lifecycle()
    assert lc.successors("a") == ["b"]


def test_lifecycle_successors_includes_implicit_cancelled() -> None:
    """If `cancelled` is in states, every cancellable state gets the implicit edge."""
    lc = Lifecycle.model_validate({
        "name": "test",
        "initial": "a",
        "terminal": ["c", "cancelled"],
        "states": {"a": {}, "b": {}, "c": {}, "cancelled": {}},
        "transitions": {"a": ["b"], "b": ["c"]},
    })
    succs = lc.successors("a")
    assert "b" in succs
    assert "cancelled" in succs


def test_lifecycle_successors_omits_cancelled_when_state_opted_out() -> None:
    lc = Lifecycle.model_validate({
        "name": "test",
        "initial": "a",
        "terminal": ["c", "cancelled"],
        "states": {"a": {"cancellable": False}, "b": {}, "c": {}, "cancelled": {}},
        "transitions": {"a": ["b"], "b": ["c"]},
    })
    succs = lc.successors("a")
    assert "cancelled" not in succs


def test_lifecycle_successors_no_cancelled_state_means_no_implicit_edge() -> None:
    lc = _minimal_lifecycle()  # no cancelled state declared
    succs = lc.successors("a")
    assert "cancelled" not in succs


def test_lifecycle_is_terminal() -> None:
    lc = _minimal_lifecycle()
    assert lc.is_terminal("c") is True
    assert lc.is_terminal("a") is False


def test_lifecycle_unknown_state_raises_on_successors() -> None:
    lc = _minimal_lifecycle()
    with pytest.raises(KeyError):
        lc.successors("ghost")
```

- [ ] **Step 2: Run, expect collection error**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/lifecycles/test_models.py -v`

Expected: FAIL — module `keel.lifecycles.models` not found.

- [ ] **Step 3: Implement `src/keel/lifecycles/models.py`**

```python
"""Pydantic schema for a phase lifecycle.

A `Lifecycle` defines a finite-state machine: a set of states (phases),
allowed transitions between them, an initial state for new projects, and one
or more terminal states.

Cancellation is implicit: if a `cancelled` state is declared, every state
where `cancellable=True` (the default) gets an implicit `<state> -> cancelled`
edge added on top of any explicit transitions.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LifecycleState(BaseModel):
    """One node in the lifecycle FSM."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = ""
    cancellable: bool = True


class Lifecycle(BaseModel):
    """A named phase lifecycle (a finite state machine over phase names)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = ""
    initial: str = Field(min_length=1)
    terminal: list[str] = Field(min_length=1)
    states: dict[str, LifecycleState] = Field(min_length=1)
    transitions: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_referenced_names(self) -> "Lifecycle":
        names = set(self.states)
        if self.initial not in names:
            raise ValueError(f"initial state '{self.initial}' is not in [states]")
        for t in self.terminal:
            if t not in names:
                raise ValueError(f"terminal state '{t}' is not in [states]")
        for src, dests in self.transitions.items():
            if src not in names:
                raise ValueError(f"transitions key '{src}' is not in [states]")
            for d in dests:
                if d not in names:
                    raise ValueError(
                        f"transitions['{src}'] contains '{d}' which is not in [states]"
                    )
        return self

    def successors(self, current: str) -> list[str]:
        """Return allowed next states from `current`, including implicit cancelled.

        Raises KeyError if `current` is not a declared state.
        """
        if current not in self.states:
            raise KeyError(current)
        explicit = list(self.transitions.get(current, []))
        if (
            "cancelled" in self.states
            and self.states[current].cancellable
            and current != "cancelled"
            and "cancelled" not in explicit
        ):
            explicit.append("cancelled")
        return explicit

    def is_terminal(self, state: str) -> bool:
        """True if `state` is in the lifecycle's terminal set."""
        return state in self.terminal
```

- [ ] **Step 4: Implement `src/keel/lifecycles/__init__.py`**

```python
"""Customizable phase lifecycles for keel.

The `default` lifecycle (the original 6 phases) ships in
`keel/lifecycles/defaults/default.toml`. Users can add their own under
`~/projects/.keel/lifecycles/<name>.toml`.
"""
from __future__ import annotations

from keel.lifecycles.models import Lifecycle, LifecycleState

__all__ = ["Lifecycle", "LifecycleState"]
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/lifecycles/test_models.py -v`

Expected: 12 PASS.

- [ ] **Step 6: Commit**

```bash
git -C ~/projects add keel/src/keel/lifecycles/ keel/tests/lifecycles/__init__.py keel/tests/lifecycles/test_models.py
git -C ~/projects commit -m "feat(keel): add Lifecycle and LifecycleState Pydantic models"
```

---

## Section 2: Default lifecycle TOML + loader

### Task 2.1: Ship `default.toml` and add `LifecycleNotFoundError`

**Files:**
- Create: `src/keel/lifecycles/defaults/__init__.py` (empty marker)
- Create: `src/keel/lifecycles/defaults/default.toml`
- Create: `tests/lifecycles/test_defaults.py`

- [ ] **Step 1: Write failing test**

Create `tests/lifecycles/test_defaults.py`:

```python
"""Tests for the shipped default lifecycle TOML."""

import tomllib
from importlib import resources

from keel.lifecycles.models import Lifecycle


def test_default_toml_shipped_in_wheel() -> None:
    """`keel.lifecycles.defaults.default.toml` is reachable via importlib.resources."""
    text = resources.files("keel.lifecycles.defaults").joinpath("default.toml").read_text()
    assert "name" in text
    assert "scoping" in text


def test_default_toml_parses_into_valid_lifecycle() -> None:
    raw = tomllib.loads(
        resources.files("keel.lifecycles.defaults").joinpath("default.toml").read_text()
    )
    lc = Lifecycle.model_validate(raw)
    assert lc.name == "default"
    assert lc.initial == "scoping"
    assert "scoping" in lc.states
    assert "designing" in lc.states
    assert "poc" in lc.states
    assert "implementing" in lc.states
    assert "shipping" in lc.states
    assert "done" in lc.states


def test_default_toml_transitions_match_legacy() -> None:
    raw = tomllib.loads(
        resources.files("keel.lifecycles.defaults").joinpath("default.toml").read_text()
    )
    lc = Lifecycle.model_validate(raw)
    # Linear walk: scoping -> designing -> poc -> implementing -> shipping -> done
    assert lc.transitions["scoping"] == ["designing"]
    assert lc.transitions["designing"] == ["poc"]
    assert lc.transitions["poc"] == ["implementing"]
    assert lc.transitions["implementing"] == ["shipping"]
    assert lc.transitions["shipping"] == ["done"]
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/lifecycles/test_defaults.py -v`

Expected: FAIL — package or file missing.

- [ ] **Step 3: Create the package marker and TOML**

`src/keel/lifecycles/defaults/__init__.py`:

```python
"""Built-in lifecycle TOMLs shipped with keel.

Files in this package are read via `importlib.resources` so they round-trip
through wheel/sdist builds.
"""
```

`src/keel/lifecycles/defaults/default.toml`:

```toml
name = "default"
description = "keel's default 6-phase lifecycle for code-adjacent projects."
initial = "scoping"
terminal = ["done", "cancelled"]

[states.scoping]
description = "Defining boundaries and success criteria."

[states.designing]
description = "Producing the technical design."

[states.poc]
description = "Building a proof-of-concept to validate the design."

[states.implementing]
description = "Production implementation."

[states.shipping]
description = "Releasing to users."

[states.done]
description = "Delivered. No further work planned."

[states.cancelled]
description = "Cancelled before completion."

[transitions]
scoping = ["designing"]
designing = ["poc"]
poc = ["implementing"]
implementing = ["shipping"]
shipping = ["done"]
```

- [ ] **Step 4: Update `pyproject.toml` to include the TOMLs in the wheel**

Read `pyproject.toml`. Find the `[tool.hatch.build.targets.wheel]` section. The current `include` line includes `_templates/*.j2`. Add the lifecycle defaults:

Current:
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/keel"]
include = ["src/keel/_templates/*.j2"]
```

Change to:
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/keel"]
include = ["src/keel/_templates/*.j2", "src/keel/lifecycles/defaults/*.toml"]
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/lifecycles/test_defaults.py -v`

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git -C ~/projects add keel/src/keel/lifecycles/defaults/ keel/pyproject.toml keel/tests/lifecycles/test_defaults.py
git -C ~/projects commit -m "feat(keel): ship default lifecycle TOML mirroring current 6 phases"
```

---

### Task 2.2: Loader with precedence chain

**Files:**
- Create: `src/keel/lifecycles/loader.py`
- Modify: `src/keel/lifecycles/__init__.py`
- Create: `tests/lifecycles/test_loader.py`

- [ ] **Step 1: Write failing tests**

Create `tests/lifecycles/test_loader.py`:

```python
"""Tests for the lifecycle loader (precedence + iteration)."""

import pytest

from keel.lifecycles import (
    Lifecycle,
    LifecycleNotFoundError,
    iter_lifecycles,
    load_lifecycle,
)


def test_load_default_from_builtin(projects) -> None:
    """`load_lifecycle('default')` returns the built-in shipped TOML."""
    lc = load_lifecycle("default")
    assert isinstance(lc, Lifecycle)
    assert lc.name == "default"
    assert lc.initial == "scoping"


def test_load_unknown_raises_lifecycle_not_found(projects) -> None:
    with pytest.raises(LifecycleNotFoundError) as exc:
        load_lifecycle("does-not-exist")
    assert "does-not-exist" in str(exc.value)


def test_load_from_user_library(projects) -> None:
    """A TOML at `<projects>/.keel/lifecycles/<name>.toml` is found."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        '''
name = "research"
description = "Research project lifecycle."
initial = "proposing"
terminal = ["published", "cancelled"]

[states.proposing]
[states.reviewing]
[states.executing]
[states.published]
[states.cancelled]

[transitions]
proposing = ["reviewing"]
reviewing = ["executing", "proposing"]
executing = ["published"]
'''.strip()
    )
    lc = load_lifecycle("research")
    assert lc.name == "research"
    assert lc.initial == "proposing"


def test_user_library_overrides_builtin(projects) -> None:
    """A user-library file with the same name as a built-in wins."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "default.toml").write_text(
        '''
name = "default"
description = "Custom default."
initial = "x"
terminal = ["y"]

[states.x]
[states.y]

[transitions]
x = ["y"]
'''.strip()
    )
    lc = load_lifecycle("default")
    # User library wins
    assert lc.initial == "x"
    assert lc.description == "Custom default."


def test_iter_lifecycles_includes_default(projects) -> None:
    items = list(iter_lifecycles())
    names = {lc.name for lc in items}
    assert "default" in names


def test_iter_lifecycles_includes_user_library(projects) -> None:
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        '''
name = "research"
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
'''.strip()
    )
    items = list(iter_lifecycles())
    names = {lc.name for lc in items}
    assert {"default", "research"} <= names


def test_iter_lifecycles_deduplicates_by_precedence(projects) -> None:
    """If the same name exists in both user library and built-ins, user wins (only one entry)."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "default.toml").write_text(
        '''
name = "default"
description = "Custom default."
initial = "x"
terminal = ["y"]
[states.x]
[states.y]
[transitions]
x = ["y"]
'''.strip()
    )
    items = [lc for lc in iter_lifecycles() if lc.name == "default"]
    assert len(items) == 1
    assert items[0].description == "Custom default."


def test_load_filename_must_match_name(projects) -> None:
    """A user-library TOML whose `name` field disagrees with its filename is rejected."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        '''
name = "different-name"
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
'''.strip()
    )
    with pytest.raises(LifecycleNotFoundError):
        load_lifecycle("research")
```

(The `projects` fixture from `keel.testing` sets `PROJECTS_DIR=tmp_path`.)

- [ ] **Step 2: Run, expect FAIL**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/lifecycles/test_loader.py -v`

Expected: FAIL — `keel.lifecycles.loader` does not exist.

- [ ] **Step 3: Implement `src/keel/lifecycles/loader.py`**

```python
"""Lifecycle lookup with precedence: user library → built-ins → plugins (deferred).

Resolution order for `load_lifecycle(name)`:

1. `<PROJECTS_DIR>/.keel/lifecycles/<name>.toml` — the user library.
2. `keel.lifecycles.defaults` package (built-in TOMLs shipped with keel).

Plugin-shipped lifecycles via the `keel.lifecycles` entry-point group are
deferred to a future plan.
"""
from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path
from typing import Iterator

from keel.lifecycles.models import Lifecycle


class LifecycleNotFoundError(LookupError):
    """Raised when no lifecycle with the given name can be found."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name

    def __str__(self) -> str:
        return f"no lifecycle named '{self.name}' (looked in user library and built-ins)"


def _user_library_dir() -> Path:
    """`<PROJECTS_DIR>/.keel/lifecycles/`. Constructed lazily so PROJECTS_DIR can be patched in tests."""
    from keel.workspace import projects_dir
    return projects_dir() / ".keel" / "lifecycles"


def _load_lifecycle_from_path(path: Path, *, expected_name: str | None = None) -> Lifecycle:
    raw = tomllib.loads(path.read_text())
    lc = Lifecycle.model_validate(raw)
    if expected_name is not None and lc.name != expected_name:
        raise LifecycleNotFoundError(expected_name)
    return lc


def load_lifecycle(name: str) -> Lifecycle:
    """Resolve a lifecycle by name through the precedence chain.

    Raises `LifecycleNotFoundError` if no match is found, or if a candidate
    file's `name` field disagrees with its filename stem.
    """
    user_path = _user_library_dir() / f"{name}.toml"
    if user_path.is_file():
        return _load_lifecycle_from_path(user_path, expected_name=name)

    builtin_dir = resources.files("keel.lifecycles.defaults")
    builtin_file = builtin_dir.joinpath(f"{name}.toml")
    if builtin_file.is_file():
        text = builtin_file.read_text()
        raw = tomllib.loads(text)
        lc = Lifecycle.model_validate(raw)
        if lc.name != name:
            raise LifecycleNotFoundError(name)
        return lc

    raise LifecycleNotFoundError(name)


def iter_lifecycles() -> Iterator[Lifecycle]:
    """Yield every reachable lifecycle. User-library entries override built-ins."""
    seen: set[str] = set()

    user_dir = _user_library_dir()
    if user_dir.is_dir():
        for path in sorted(user_dir.glob("*.toml")):
            try:
                lc = _load_lifecycle_from_path(path, expected_name=path.stem)
            except Exception:
                continue
            if lc.name in seen:
                continue
            seen.add(lc.name)
            yield lc

    builtin_dir = resources.files("keel.lifecycles.defaults")
    for entry in sorted(builtin_dir.iterdir(), key=lambda p: p.name):
        if not entry.name.endswith(".toml"):
            continue
        text = entry.read_text()
        try:
            raw = tomllib.loads(text)
            lc = Lifecycle.model_validate(raw)
        except Exception:
            continue
        if lc.name in seen:
            continue
        seen.add(lc.name)
        yield lc
```

- [ ] **Step 4: Re-export from `src/keel/lifecycles/__init__.py`**

```python
"""Customizable phase lifecycles for keel.

The `default` lifecycle (the original 6 phases) ships in
`keel/lifecycles/defaults/default.toml`. Users can add their own under
`~/projects/.keel/lifecycles/<name>.toml`.
"""
from __future__ import annotations

from keel.lifecycles.loader import (
    LifecycleNotFoundError,
    iter_lifecycles,
    load_lifecycle,
)
from keel.lifecycles.models import Lifecycle, LifecycleState

__all__ = [
    "Lifecycle",
    "LifecycleNotFoundError",
    "LifecycleState",
    "iter_lifecycles",
    "load_lifecycle",
]
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/lifecycles/test_loader.py -v`

Expected: 8 PASS.

- [ ] **Step 6: Commit**

```bash
git -C ~/projects add keel/src/keel/lifecycles/ keel/tests/lifecycles/test_loader.py
git -C ~/projects commit -m "feat(keel): add lifecycle loader with user-library + built-in precedence"
```

---

## Section 3: Backward-compat shim and API exports

### Task 3.1: Make `keel.lifecycle` PHASES/next_phase/is_valid_phase delegate to the default lifecycle

**Files:**
- Modify: `src/keel/lifecycle.py`
- Modify: `tests/test_lifecycle.py`

- [ ] **Step 1: Read current state of `src/keel/lifecycle.py`**

Inspect what's there: `PHASES`, `DEFAULT_PHASE`, `next_phase`, `is_valid_phase`, plus the milestone/task constants. Only the phase-related symbols change; the milestone/task ones stay untouched.

- [ ] **Step 2: Add a regression test before changing**

Append to `tests/test_lifecycle.py`:

```python
def test_phases_match_default_lifecycle() -> None:
    """PHASES is derived from the default lifecycle's transitions, in linear order."""
    from keel.lifecycle import PHASES
    assert PHASES == ["scoping", "designing", "poc", "implementing", "shipping", "done"]


def test_default_phase_is_default_lifecycle_initial() -> None:
    from keel.lifecycle import DEFAULT_PHASE
    assert DEFAULT_PHASE == "scoping"


def test_next_phase_walks_default_lifecycle() -> None:
    from keel.lifecycle import next_phase
    assert next_phase("scoping") == "designing"
    assert next_phase("designing") == "poc"
    assert next_phase("done") is None
    assert next_phase("ghost") is None  # unknown phases return None


def test_is_valid_phase_uses_default_lifecycle() -> None:
    from keel.lifecycle import is_valid_phase
    assert is_valid_phase("scoping")
    assert is_valid_phase("done")
    assert not is_valid_phase("ghost")
    # `cancelled` is in the default lifecycle's states (it's terminal).
    assert is_valid_phase("cancelled")
```

(The previous `is_valid_phase("cancelled")` may have returned False in pre-Plan-7 keel because the original `PHASES` list didn't include it. The default.toml DOES declare `cancelled`. This test pins the new behavior.)

- [ ] **Step 3: Run tests, see which pre-existing tests fail**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/test_lifecycle.py -v`

Expected: most existing tests pass; the new `test_is_valid_phase_uses_default_lifecycle` may fail because `cancelled` is currently not in `PHASES`. That's the change we're making — test should pass after step 4.

- [ ] **Step 4: Modify `src/keel/lifecycle.py` to delegate**

The phase-related portion changes from hardcoded lists to wrappers around `load_lifecycle("default")`. Replace the existing `PHASES`, `DEFAULT_PHASE`, `next_phase`, `is_valid_phase` definitions with:

```python
def _default_lifecycle():
    """Lazy accessor; the loader has its own caching by virtue of being deterministic."""
    from keel.lifecycles import load_lifecycle
    return load_lifecycle("default")


def _default_phases() -> list[str]:
    """Return the default lifecycle's states in linear `transitions` order.

    Walks `transitions` from `initial` until a state has no successor or the chain
    revisits a state. Used to produce the legacy `PHASES` list shape.
    """
    lc = _default_lifecycle()
    out: list[str] = []
    seen: set[str] = set()
    cur: str | None = lc.initial
    while cur is not None and cur not in seen:
        out.append(cur)
        seen.add(cur)
        nexts = lc.transitions.get(cur, [])
        cur = nexts[0] if nexts else None
    return out


# Backward-compatible top-level constants. Computed at import time; if a user
# tweaks the default lifecycle TOML, restart the process to pick up changes.
PHASES: list[str] = _default_phases()
DEFAULT_PHASE: str = _default_lifecycle().initial


def next_phase(current: str) -> str | None:
    """Return the next phase in the default lifecycle, or None at the end."""
    lc = _default_lifecycle()
    if current not in lc.states:
        return None
    nexts = lc.transitions.get(current, [])
    return nexts[0] if nexts else None


def is_valid_phase(name: str) -> bool:
    """True if `name` is a state in the default lifecycle."""
    return name in _default_lifecycle().states
```

(Leave the milestone/task constants — `MILESTONE_STATES`, `TASK_STATES`, etc. — untouched.)

- [ ] **Step 5: Run tests**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/test_lifecycle.py -v`

Expected: all PASS, including the new tests.

- [ ] **Step 6: Run full suite to catch regressions**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short`

Expected: 442 + 12 (models) + 3 (defaults) + 8 (loader) + 4 (lifecycle delegation) = 469 tests pass.

- [ ] **Step 7: Commit**

```bash
git -C ~/projects add keel/src/keel/lifecycle.py keel/tests/test_lifecycle.py
git -C ~/projects commit -m "feat(keel): keel.lifecycle PHASES/next_phase/is_valid_phase delegate to default lifecycle"
```

---

### Task 3.2: Export new symbols from `keel.api`

**Files:**
- Modify: `src/keel/api.py`

- [ ] **Step 1: Add imports**

Read `src/keel/api.py` and find the existing import block. Add:

```python
from keel.lifecycles import (
    Lifecycle,
    LifecycleNotFoundError,
    LifecycleState,
    iter_lifecycles,
    load_lifecycle,
)
```

- [ ] **Step 2: Add to `__all__`**

Under a new comment heading `# Lifecycles (FSM)`, add:

```python
"Lifecycle", "LifecycleNotFoundError", "LifecycleState",
"iter_lifecycles", "load_lifecycle",
```

- [ ] **Step 3: Verify tests pass + lint**

Run:
- `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short`
- `cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests`
- `cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff format --check src tests`

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git -C ~/projects add keel/src/keel/api.py
git -C ~/projects commit -m "feat(keel): export Lifecycle, LifecycleState, load_lifecycle, iter_lifecycles, LifecycleNotFoundError from keel.api"
```

---

## Section 4: Manifest field + `keel new --lifecycle`

### Task 4.1: Add `lifecycle: str = "default"` to `ProjectMeta`

**Files:**
- Modify: `src/keel/manifest/models.py`
- Modify: `tests/test_manifest.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_manifest.py`:

```python
def test_project_meta_lifecycle_defaults_to_default() -> None:
    """ProjectMeta picks 'default' when the lifecycle field is omitted."""
    from datetime import date
    from keel.manifest import ProjectMeta
    m = ProjectMeta(name="foo", description="x", created=date(2026, 5, 1))
    assert m.lifecycle == "default"


def test_project_meta_lifecycle_custom_value() -> None:
    from datetime import date
    from keel.manifest import ProjectMeta
    m = ProjectMeta(name="foo", description="x", created=date(2026, 5, 1), lifecycle="research")
    assert m.lifecycle == "research"


def test_project_manifest_lifecycle_round_trip(tmp_path) -> None:
    """The lifecycle field round-trips through the TOML save/load cycle."""
    from datetime import date
    from keel.manifest import (
        ProjectManifest, ProjectMeta,
        load_project_manifest, save_project_manifest,
    )
    path = tmp_path / "project.toml"
    original = ProjectManifest(
        project=ProjectMeta(
            name="foo", description="x", created=date(2026, 5, 1), lifecycle="research"
        ),
        repos=[],
    )
    save_project_manifest(path, original)
    loaded = load_project_manifest(path)
    assert loaded.project.lifecycle == "research"


def test_project_manifest_pre_v1_no_lifecycle_field(tmp_path) -> None:
    """An existing TOML without [project] lifecycle = ... still loads (defaults to 'default')."""
    from keel.manifest import load_project_manifest
    path = tmp_path / "project.toml"
    path.write_text(
        '''
[project]
name = "foo"
description = "x"
created = 2026-05-01
'''.strip()
    )
    m = load_project_manifest(path)
    assert m.project.lifecycle == "default"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/test_manifest.py::test_project_meta_lifecycle_defaults_to_default -v`

Expected: FAIL — `ProjectMeta` has no `lifecycle` field.

- [ ] **Step 3: Add the field to `ProjectMeta`**

In `src/keel/manifest/models.py`, locate the `ProjectMeta` class and add the field. The current class:

```python
class ProjectMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    created: _date
```

Becomes:

```python
class ProjectMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    created: _date
    lifecycle: str = Field(default="default", description="Name of the phase lifecycle.")
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/test_manifest.py -v`

Expected: all PASS, including the 4 new tests.

- [ ] **Step 5: Run full suite**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short`

Expected: prior tests + the 4 new ones pass.

- [ ] **Step 6: Commit**

```bash
git -C ~/projects add keel/src/keel/manifest/models.py keel/tests/test_manifest.py
git -C ~/projects commit -m "feat(keel): add lifecycle field to ProjectMeta (default 'default')"
```

---

### Task 4.2: `keel new --lifecycle <name>` flag

**Files:**
- Modify: `src/keel/commands/new.py`
- Modify: `tests/commands/test_new.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/test_new.py`:

```python
def test_new_records_lifecycle_in_manifest(projects, monkeypatch) -> None:
    """`keel new <name> --lifecycle <id>` writes the field to project.toml."""
    monkeypatch.chdir(projects)
    runner.invoke(
        app, ["new", "alpha", "-d", "test", "--no-worktree", "-y", "--lifecycle", "default"]
    )
    from keel.manifest import load_project_manifest
    m = load_project_manifest(projects / "alpha" / "design" / "project.toml")
    assert m.project.lifecycle == "default"


def test_new_default_lifecycle_when_omitted(projects, monkeypatch) -> None:
    """When --lifecycle is omitted, the manifest gets 'default'."""
    monkeypatch.chdir(projects)
    runner.invoke(app, ["new", "alpha", "-d", "test", "--no-worktree", "-y"])
    from keel.manifest import load_project_manifest
    m = load_project_manifest(projects / "alpha" / "design" / "project.toml")
    assert m.project.lifecycle == "default"


def test_new_unknown_lifecycle_fails(projects, monkeypatch) -> None:
    """`--lifecycle ghost` exits non-zero with a clear error."""
    monkeypatch.chdir(projects)
    result = runner.invoke(
        app, ["new", "alpha", "-d", "test", "--no-worktree", "-y", "--lifecycle", "ghost"]
    )
    assert result.exit_code != 0
    assert "ghost" in result.stderr.lower() or "lifecycle" in result.stderr.lower()


def test_new_uses_lifecycle_initial_phase(projects, make_project, monkeypatch) -> None:
    """The new project's `.phase` file is set to the lifecycle's initial state."""
    # Create a custom lifecycle with a non-'scoping' initial state.
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        '''
name = "research"
initial = "proposing"
terminal = ["published"]
[states.proposing]
[states.published]
[transitions]
proposing = ["published"]
'''.strip()
    )
    monkeypatch.chdir(projects)
    runner.invoke(
        app, ["new", "alpha", "-d", "test", "--no-worktree", "-y", "--lifecycle", "research"]
    )
    phase_text = (projects / "alpha" / "design" / ".phase").read_text().strip()
    assert phase_text == "proposing"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_new.py::test_new_records_lifecycle_in_manifest -v`

Expected: FAIL — `--lifecycle` is not a known option.

- [ ] **Step 3: Update `cmd_new`**

In `src/keel/commands/new.py`, locate the `cmd_new` signature. Add a `lifecycle` parameter near the existing options:

```python
lifecycle: str = typer.Option(
    "default", "--lifecycle",
    help="Phase lifecycle to use for this project. See 'keel lifecycle list'.",
),
```

After scope validation but before the manifest write, validate that the named lifecycle exists:

```python
from keel.api import LifecycleNotFoundError, load_lifecycle

try:
    lc = load_lifecycle(lifecycle)
except LifecycleNotFoundError:
    out.fail(
        f"unknown lifecycle '{lifecycle}' "
        "(run 'keel lifecycle list' to see available options)",
        code=ErrorCode.NOT_FOUND,
    )
```

Then plumb the value into the `ProjectMeta` constructor:

```python
ProjectMeta(name=name, description=description, created=date.today(), lifecycle=lifecycle)
```

And use the lifecycle's initial state for the `.phase` file:

```python
(design_dir / ".phase").write_text(f"{lc.initial}\n")
```

(Replacing whatever currently writes `scoping` directly.)

- [ ] **Step 4: Run tests**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_new.py -v`

Expected: all PASS.

- [ ] **Step 5: Run full suite + lint**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff format --check src tests
```

- [ ] **Step 6: Commit**

```bash
git -C ~/projects add keel/src/keel/commands/new.py keel/tests/commands/test_new.py
git -C ~/projects commit -m "feat(keel): keel new --lifecycle <name> picks the phase lifecycle"
```

---

## Section 5: Wire FSM into `keel phase`

### Task 5.1: Use `Lifecycle.successors()` for transitions and `--list-next`

**Files:**
- Modify: `src/keel/commands/phase.py`
- Modify: `tests/commands/test_phase.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/commands/test_phase.py`:

```python
def test_phase_uses_project_lifecycle_for_transitions(projects, make_project, monkeypatch) -> None:
    """When the project picks a custom lifecycle, transitions follow that FSM."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        '''
name = "research"
initial = "proposing"
terminal = ["published", "cancelled"]
[states.proposing]
[states.reviewing]
[states.published]
[states.cancelled]
[transitions]
proposing = ["reviewing"]
reviewing = ["published", "proposing"]
'''.strip()
    )
    monkeypatch.chdir(projects)
    runner.invoke(app, ["new", "alpha", "-d", "x", "--no-worktree", "-y", "--lifecycle", "research"])
    monkeypatch.chdir(projects / "alpha" / "design")

    # Initial phase should be 'proposing'
    result = runner.invoke(app, ["phase", "--list-next", "--json"])
    import json
    data = json.loads(result.stdout)
    assert data["current"] == "proposing"
    # Cancelled is implicit (cancellable=true by default)
    assert set(data["next"]) == {"reviewing", "cancelled"}


def test_phase_list_next_branching(projects, make_project, monkeypatch) -> None:
    """A branching state shows multiple successors."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "branchy.toml").write_text(
        '''
name = "branchy"
initial = "a"
terminal = ["c"]
[states.a]
[states.b]
[states.c]
[transitions]
a = ["b", "c"]
'''.strip()
    )
    monkeypatch.chdir(projects)
    runner.invoke(app, ["new", "alpha", "-d", "x", "--no-worktree", "-y", "--lifecycle", "branchy"])
    monkeypatch.chdir(projects / "alpha" / "design")
    import json
    result = runner.invoke(app, ["phase", "--list-next", "--json"])
    data = json.loads(result.stdout)
    assert data["current"] == "a"
    assert set(data["next"]) == {"b", "c"}


def test_phase_rejects_invalid_target(projects, make_project, monkeypatch) -> None:
    """Trying to advance to a state not reachable from current fails."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "linear.toml").write_text(
        '''
name = "linear"
initial = "a"
terminal = ["c"]
[states.a]
[states.b]
[states.c]
[transitions]
a = ["b"]
b = ["c"]
'''.strip()
    )
    monkeypatch.chdir(projects)
    runner.invoke(app, ["new", "alpha", "-d", "x", "--no-worktree", "-y", "--lifecycle", "linear"])
    monkeypatch.chdir(projects / "alpha" / "design")
    # 'a' has no edge to 'c' — should fail
    result = runner.invoke(app, ["phase", "c", "--force"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run, expect FAIL**

Expected: tests fail because `phase` currently uses the hardcoded `next_phase()` rather than the project's lifecycle.

- [ ] **Step 3: Update `src/keel/commands/phase.py`**

Read the current phase command. Replace the `next_phase()`-based logic with lifecycle-aware logic.

Key changes:

a) **Resolve the project's lifecycle**. After scope resolution, load the project manifest to read `manifest.project.lifecycle`, then `load_lifecycle(name)`. Cache as `lc`.

b) **Update `--list-next`**. Replace:

```python
next_p = next_phase(current)
nexts = [next_p] if next_p is not None else []
```

with:

```python
nexts = lc.successors(current) if current in lc.states else []
```

c) **Update `--next` (auto-advance)**. Currently picks `next_phase(current)`. Now pick `lc.successors(current)[0]` (first explicit successor; falls back to nothing if state is terminal). Since `cancelled` may be in `successors()`, filter it out for `--next` (we don't auto-cancel):

```python
explicit_successors = [s for s in lc.successors(current) if s != "cancelled"]
if not explicit_successors:
    out.fail(
        f"no forward transition from '{current}' (state is terminal or has no non-cancel edges)",
        code=ErrorCode.END_OF_LIFECYCLE,
    )
target = explicit_successors[0]
```

d) **Update target-state validation**. When the user passes a target state, validate it's in `lc.successors(current)` (or matches `current` for no-op):

```python
if target != current and target not in lc.successors(current):
    out.fail(
        f"cannot transition from '{current}' to '{target}' "
        f"(allowed: {', '.join(lc.successors(current)) or 'none'})",
        code=ErrorCode.INVALID_STATE,
    )
```

The existing `is_valid_phase()` check (against the default lifecycle) should be removed in favor of `target in lc.states`:

```python
if target not in lc.states:
    out.fail(
        f"unknown phase '{target}' for lifecycle '{lc.name}'",
        code=ErrorCode.INVALID_PHASE,
    )
```

e) **Backward transitions**: keep the existing pattern — backward transitions need a confirm prompt (unless `--force` or matching successor lookup permits them already).

Actually with the FSM model, "backward" is just any successor that the user added explicitly. If a user defines `reviewing -> ["published", "proposing"]`, then `proposing` is a legitimate successor of `reviewing` per the FSM. No special "backward" handling needed.

(If the existing `cmd_phase` has code for "backward transitions" with a confirm prompt, you can remove it — the FSM is now the source of truth for which moves are valid.)

- [ ] **Step 4: Run tests**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest tests/commands/test_phase.py -v`

Expected: all PASS, including the 3 new tests AND the existing tests (which use the default lifecycle and should still work).

- [ ] **Step 5: Run full suite + lint**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff format --check src tests
```

- [ ] **Step 6: Commit**

```bash
git -C ~/projects add keel/src/keel/commands/phase.py keel/tests/commands/test_phase.py
git -C ~/projects commit -m "feat(keel): keel phase uses the project's lifecycle FSM for transitions"
```

---

## Section 6: `keel lifecycle` command group

### Task 6.1: Scaffold the `lifecycle` subapp

**Files:**
- Create: `src/keel/commands/lifecycle/__init__.py`
- Create: `tests/commands/lifecycle/__init__.py` (empty marker)
- Modify: `src/keel/app.py`

- [ ] **Step 1: Create the subapp**

`src/keel/commands/lifecycle/__init__.py`:

```python
"""`keel lifecycle ...` command group."""
from __future__ import annotations

import typer

app = typer.Typer(
    name="lifecycle",
    help="Inspect and manage phase lifecycles.",
    no_args_is_help=True,
)
```

`tests/commands/lifecycle/__init__.py` — empty file (just creates the package).

- [ ] **Step 2: Register in `src/keel/app.py`**

After the existing subapp registrations (e.g. after `manifest_app`), add:

```python
from keel.commands.lifecycle import app as lifecycle_app  # noqa: E402

app.add_typer(lifecycle_app, name="lifecycle")
```

- [ ] **Step 3: Smoke check**

Run: `cd /Users/andrei.matei/projects/keel && uv run --extra dev keel lifecycle --help`

Expected: shows the lifecycle subgroup with no subcommands yet.

- [ ] **Step 4: Commit**

```bash
git -C ~/projects add keel/src/keel/commands/lifecycle/__init__.py keel/tests/commands/lifecycle/__init__.py keel/src/keel/app.py
git -C ~/projects commit -m "feat(keel): scaffold keel lifecycle command group"
```

---

### Task 6.2: `keel lifecycle list`

**Files:**
- Create: `src/keel/commands/lifecycle/list.py`
- Modify: `src/keel/commands/lifecycle/__init__.py`
- Create: `tests/commands/lifecycle/test_list.py`

- [ ] **Step 1: Write failing tests**

`tests/commands/lifecycle/test_list.py`:

```python
"""Tests for `keel lifecycle list`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_list_includes_default(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    names = {lc["name"] for lc in data["lifecycles"]}
    assert "default" in names


def test_list_includes_user_library(projects) -> None:
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        '''
name = "research"
description = "Research."
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
'''.strip()
    )
    result = runner.invoke(app, ["lifecycle", "list", "--json"])
    data = json.loads(result.stdout)
    entry = next((lc for lc in data["lifecycles"] if lc["name"] == "research"), None)
    assert entry is not None
    assert entry["source"] == "user"
    assert entry["description"] == "Research."


def test_list_human_format(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "list"])
    assert result.exit_code == 0
    assert "default" in result.stdout
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement `src/keel/commands/lifecycle/list.py`**

```python
"""`keel lifecycle list` — enumerate available lifecycles."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from keel.api import Output, iter_lifecycles
from keel.workspace import projects_dir


def _source_for(name: str) -> str:
    """Return 'user' if the user library has a TOML for this name, else 'builtin'."""
    user_path = projects_dir() / ".keel" / "lifecycles" / f"{name}.toml"
    if user_path.is_file():
        return "user"
    return "builtin"


def cmd_list(
    ctx: typer.Context,
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """List all available lifecycles (built-ins + user library)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    rows: list[dict[str, str]] = []
    for lc in iter_lifecycles():
        rows.append({
            "name": lc.name,
            "description": lc.description,
            "source": _source_for(lc.name),
            "states": str(len(lc.states)),
            "initial": lc.initial,
        })

    if json_mode:
        out.result({"lifecycles": rows})
        return

    table = Table()
    table.add_column("Name")
    table.add_column("Source")
    table.add_column("States")
    table.add_column("Initial")
    table.add_column("Description")
    for r in rows:
        table.add_row(r["name"], r["source"], r["states"], r["initial"], r["description"])
    out.print_rich(table)
```

- [ ] **Step 4: Register in `__init__.py`**

Append to `src/keel/commands/lifecycle/__init__.py`:

```python
from keel.commands.lifecycle.list import cmd_list  # noqa: E402

app.command(name="list")(cmd_list)
```

- [ ] **Step 5: Run tests**

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git -C ~/projects add keel/src/keel/commands/lifecycle/list.py keel/src/keel/commands/lifecycle/__init__.py keel/tests/commands/lifecycle/test_list.py
git -C ~/projects commit -m "feat(keel): add 'keel lifecycle list' command"
```

---

### Task 6.3: `keel lifecycle show <name>`

**Files:**
- Create: `src/keel/commands/lifecycle/show.py`
- Modify: `src/keel/commands/lifecycle/__init__.py`
- Create: `tests/commands/lifecycle/test_show.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for `keel lifecycle show`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_show_default(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "show", "default", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["name"] == "default"
    assert data["initial"] == "scoping"
    assert "scoping" in data["states"]


def test_show_human_includes_transitions(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "show", "default"])
    assert result.exit_code == 0
    assert "scoping" in result.stdout
    assert "designing" in result.stdout


def test_show_unknown_fails(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "show", "ghost"])
    assert result.exit_code != 0
    assert "ghost" in result.stderr.lower() or "lifecycle" in result.stderr.lower()
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement `src/keel/commands/lifecycle/show.py`**

```python
"""`keel lifecycle show <name>` — print a lifecycle's states and transitions."""
from __future__ import annotations

import typer
from rich.table import Table

from keel.api import (
    ErrorCode,
    LifecycleNotFoundError,
    Output,
    load_lifecycle,
)


def cmd_show(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Lifecycle name."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Show a lifecycle's states, terminal set, and transitions."""
    out = Output.from_context(ctx, json_mode=json_mode)
    try:
        lc = load_lifecycle(name)
    except LifecycleNotFoundError as e:
        out.fail(str(e), code=ErrorCode.NOT_FOUND)

    if json_mode:
        out.result(lc.model_dump())
        return

    out.info(f"Lifecycle: {lc.name}")
    if lc.description:
        out.info(f"  {lc.description}")
    out.info(f"Initial: {lc.initial}")
    out.info(f"Terminal: {', '.join(lc.terminal)}")

    table = Table(title="Transitions")
    table.add_column("From")
    table.add_column("To")
    for src in lc.states:
        succs = lc.successors(src)
        if not succs:
            continue
        table.add_row(src, ", ".join(succs))
    out.print_rich(table)
```

- [ ] **Step 4: Register**

Append to `src/keel/commands/lifecycle/__init__.py`:

```python
from keel.commands.lifecycle.show import cmd_show  # noqa: E402

app.command(name="show")(cmd_show)
```

- [ ] **Step 5: Run tests**

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git -C ~/projects add keel/src/keel/commands/lifecycle/show.py keel/src/keel/commands/lifecycle/__init__.py keel/tests/commands/lifecycle/test_show.py
git -C ~/projects commit -m "feat(keel): add 'keel lifecycle show' command"
```

---

### Task 6.4: `keel lifecycle validate <path>`

**Files:**
- Create: `src/keel/commands/lifecycle/validate.py`
- Modify: `src/keel/commands/lifecycle/__init__.py`
- Create: `tests/commands/lifecycle/test_validate.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for `keel lifecycle validate`."""

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_validate_valid_toml(tmp_path) -> None:
    f = tmp_path / "research.toml"
    f.write_text(
        '''
name = "research"
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
'''.strip()
    )
    result = runner.invoke(app, ["lifecycle", "validate", str(f)])
    assert result.exit_code == 0
    assert "valid" in result.stdout.lower() or "OK" in result.stdout


def test_validate_unknown_initial_state_fails(tmp_path) -> None:
    f = tmp_path / "broken.toml"
    f.write_text(
        '''
name = "broken"
initial = "ghost"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
'''.strip()
    )
    result = runner.invoke(app, ["lifecycle", "validate", str(f)])
    assert result.exit_code != 0


def test_validate_filename_mismatch_warns(tmp_path) -> None:
    """If the TOML's `name` differs from the filename stem, warn but don't fail."""
    f = tmp_path / "research.toml"
    f.write_text(
        '''
name = "different-name"
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
'''.strip()
    )
    result = runner.invoke(app, ["lifecycle", "validate", str(f)])
    # Validation passes (the schema is fine), but a warning surfaces.
    combined = (result.stdout + result.stderr).lower()
    assert "warning" in combined or "mismatch" in combined or "filename" in combined


def test_validate_missing_file_fails(tmp_path) -> None:
    result = runner.invoke(app, ["lifecycle", "validate", str(tmp_path / "nope.toml")])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement `src/keel/commands/lifecycle/validate.py`**

```python
"""`keel lifecycle validate <path>` — lint a lifecycle TOML offline."""
from __future__ import annotations

import tomllib
from pathlib import Path

import typer

from keel.api import ErrorCode, Output
from keel.lifecycles.models import Lifecycle


def cmd_validate(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Path to a lifecycle TOML."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Validate a lifecycle TOML against the Lifecycle schema."""
    out = Output.from_context(ctx, json_mode=json_mode)

    if not path.is_file():
        out.fail(f"file not found: {path}", code=ErrorCode.NOT_FOUND)

    try:
        raw = tomllib.loads(path.read_text())
    except Exception as e:
        out.fail(f"invalid TOML: {e}", code=ErrorCode.INVALID_STATE)

    try:
        lc = Lifecycle.model_validate(raw)
    except Exception as e:
        out.fail(f"lifecycle invalid: {e}", code=ErrorCode.INVALID_STATE)

    if lc.name != path.stem:
        out.warn(
            f"lifecycle name '{lc.name}' does not match filename stem '{path.stem}' "
            "(load_lifecycle would not find this file by '{path.stem}')"
        )

    out.result(
        {"path": str(path), "name": lc.name, "valid": True},
        human_text=f"OK — lifecycle valid: {lc.name} ({path})",
    )
```

- [ ] **Step 4: Register**

Append to `__init__.py`:

```python
from keel.commands.lifecycle.validate import cmd_validate  # noqa: E402

app.command(name="validate")(cmd_validate)
```

- [ ] **Step 5: Run tests**

Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git -C ~/projects add keel/src/keel/commands/lifecycle/validate.py keel/src/keel/commands/lifecycle/__init__.py keel/tests/commands/lifecycle/test_validate.py
git -C ~/projects commit -m "feat(keel): add 'keel lifecycle validate' to lint TOMLs offline"
```

---

### Task 6.5: `keel lifecycle init <name>`

**Files:**
- Create: `src/keel/commands/lifecycle/init.py`
- Create: `src/keel/_templates/lifecycle.toml.j2`
- Modify: `src/keel/commands/lifecycle/__init__.py`
- Create: `tests/commands/lifecycle/test_init.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for `keel lifecycle init`."""

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_init_creates_template_in_user_library(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "init", "research"])
    assert result.exit_code == 0
    target = projects / ".keel" / "lifecycles" / "research.toml"
    assert target.is_file()
    text = target.read_text()
    assert 'name = "research"' in text


def test_init_refuses_to_overwrite(projects) -> None:
    """A second `init` of the same name fails unless --force."""
    runner.invoke(app, ["lifecycle", "init", "research"])
    result = runner.invoke(app, ["lifecycle", "init", "research"])
    assert result.exit_code != 0


def test_init_force_overwrites(projects) -> None:
    runner.invoke(app, ["lifecycle", "init", "research"])
    target = projects / ".keel" / "lifecycles" / "research.toml"
    target.write_text("# user edits")
    result = runner.invoke(app, ["lifecycle", "init", "research", "--force"])
    assert result.exit_code == 0
    assert "user edits" not in target.read_text()


def test_init_validates_after_writing(projects) -> None:
    """The scaffolded file should pass `keel lifecycle validate`."""
    runner.invoke(app, ["lifecycle", "init", "research"])
    target = projects / ".keel" / "lifecycles" / "research.toml"
    result = runner.invoke(app, ["lifecycle", "validate", str(target)])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Create the Jinja template**

`src/keel/_templates/lifecycle.toml.j2`:

```jinja
name = "{{ name }}"
description = "TODO: describe this lifecycle."
initial = "draft"
terminal = ["done", "cancelled"]

[states.draft]
description = "Initial state for new projects."

[states.in-progress]
description = "Active work."

[states.done]
description = "Completed."

[states.cancelled]
description = "Cancelled before completion."

[transitions]
draft = ["in-progress"]
in-progress = ["done"]
# Implicit: any state -> "cancelled" (the cancelled state is declared).
```

- [ ] **Step 4: Implement `src/keel/commands/lifecycle/init.py`**

```python
"""`keel lifecycle init <name>` — scaffold a new lifecycle TOML in the user library."""
from __future__ import annotations

import typer

from keel import templates
from keel.api import ErrorCode, Output
from keel.workspace import projects_dir


def cmd_init(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Lifecycle name (also the filename stem)."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file with this name."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Scaffold `<projects-dir>/.keel/lifecycles/<name>.toml` with placeholder states."""
    out = Output.from_context(ctx, json_mode=json_mode)

    target_dir = projects_dir() / ".keel" / "lifecycles"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}.toml"

    if target.exists() and not force:
        out.fail(
            f"{target} already exists (use --force to overwrite)",
            code=ErrorCode.EXISTS,
        )

    target.write_text(templates.render("lifecycle.toml.j2", name=name))
    out.result(
        {"path": str(target), "name": name},
        human_text=f"Scaffolded: {target}",
    )
```

- [ ] **Step 5: Register**

Append to `__init__.py`:

```python
from keel.commands.lifecycle.init import cmd_init  # noqa: E402

app.command(name="init")(cmd_init)
```

- [ ] **Step 6: Run tests**

Expected: 4 PASS.

- [ ] **Step 7: Run full suite + lint**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff format --check src tests
```

- [ ] **Step 8: Commit**

```bash
git -C ~/projects add keel/src/keel/commands/lifecycle/init.py keel/src/keel/commands/lifecycle/__init__.py keel/src/keel/_templates/lifecycle.toml.j2 keel/tests/commands/lifecycle/test_init.py
git -C ~/projects commit -m "feat(keel): add 'keel lifecycle init' to scaffold a new TOML"
```

---

## Section 7: Documentation

### Task 7.1: README and CONTRIBUTING updates

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: README — add a lifecycles section**

Find the existing roadmap or features section and append a new section after the milestones+tasks workflow:

```markdown
## Customizable phase lifecycles

By default, projects use a 6-phase lifecycle:
`scoping → designing → poc → implementing → shipping → done`. You can define
custom lifecycles as TOML files under `~/projects/.keel/lifecycles/<name>.toml`
and pick one at project creation:

```bash
keel lifecycle init research        # scaffold a starter TOML
$EDITOR ~/projects/.keel/lifecycles/research.toml
keel lifecycle validate ~/projects/.keel/lifecycles/research.toml
keel new my-paper -d "Q3 paper" --lifecycle research
keel phase --list-next               # follows the FSM you defined
```

Inspect what's available:

```bash
keel lifecycle list
keel lifecycle show default
```

A lifecycle is modelled as a finite-state machine: a set of named states,
allowed transitions between them, an initial state for new projects, and
terminal states. If a `cancelled` state is declared, every state with
`cancellable = true` (the default) gets an implicit `<state> → cancelled`
edge; lifecycles without a `cancelled` state simply don't support
cancellation.
```

- [ ] **Step 2: CONTRIBUTING — add a "Custom lifecycles" subsection**

Under "Authoring a plugin" (or as a sibling section), add:

```markdown
## Authoring a custom lifecycle

Custom workflows live as TOML files under
`~/projects/.keel/lifecycles/<name>.toml`. They override built-ins of the
same name. Schema fields:

- `name` (string, required): must match the filename stem.
- `description` (string, optional).
- `initial` (string, required): starting state for new projects.
- `terminal` (list[string], required): one or more states marking completion.
- `[states.<name>]` (one per state): supports `description` and
  `cancellable` (default `true`).
- `[transitions]` (table): `<from> = ["<to1>", "<to2>", ...]`.

An example minimal lifecycle:

```toml
name = "research"
description = "Research project lifecycle."
initial = "proposing"
terminal = ["published", "cancelled"]

[states.proposing]
[states.reviewing]
[states.executing]
[states.published]
[states.cancelled]

[transitions]
proposing = ["reviewing"]
reviewing = ["executing", "proposing"]
executing = ["published"]
```

Run `keel lifecycle validate <path>` to lint a TOML; `keel lifecycle init
<name>` scaffolds a placeholder.
```

- [ ] **Step 3: Commit**

```bash
git -C ~/projects add keel/README.md keel/CONTRIBUTING.md
git -C ~/projects commit -m "docs(keel): document customizable lifecycles in README and CONTRIBUTING"
```

---

## Section 8: Smoke + tag

### Task 8.1: End-to-end smoke + tag

- [ ] **Step 1: Run full suite + lint + format**

```
cd /Users/andrei.matei/projects/keel && uv run --extra dev pytest --tb=short
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff check src tests
cd /Users/andrei.matei/projects/keel && uv run --extra dev ruff format --check src tests
```

Expected: ~485+ tests pass; clean.

- [ ] **Step 2: End-to-end smoke**

```bash
SMOKE_DIR=$(mktemp -d -t keel-p7-smoke-XXXXXX)

# Scaffold a custom lifecycle
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel lifecycle init research
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel lifecycle validate $SMOKE_DIR/.keel/lifecycles/research.toml

# Create a project using it
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel new alpha -d "test" --no-worktree -y --lifecycle research

# Inspect transitions
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel phase --list-next --json --project alpha

# List available lifecycles
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel lifecycle list

# Verify default still works
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel new beta -d "default" --no-worktree -y
PROJECTS_DIR=$SMOKE_DIR uv run --extra dev keel phase --list-next --json --project beta
```

Expected: research project starts in `draft`, beta project starts in `scoping`. All commands exit 0.

- [ ] **Step 3: Tag**

```bash
git -C ~/projects tag keel-plan-7
```

(Sync to public + push handled outside this plan.)

---

## Self-review

| Spec section | Implementing tasks |
|---|---|
| Lifecycle schema (name, initial, terminal, states, transitions, cancellable, implicit cancellation) | Task 1.1 (models with validators), Task 2.1 (default.toml example) |
| Lookup precedence (project → user library → built-ins) | Task 2.2 (loader) |
| Built-in `default` mirrors the current 6 phases | Task 2.1 (default.toml) |
| `keel new --lifecycle <name>` | Task 4.2 |
| `keel lifecycle list/show/validate/init` | Tasks 6.2, 6.3, 6.4, 6.5 |
| `keel phase --list-next` returns FSM successors | Task 5.1 |
| `keel phase <target>` rejects invalid transitions | Task 5.1 |
| Backward compat: existing projects default to "default" | Task 4.1 (Pydantic default) |
| `keel.lifecycle.PHASES`/`next_phase`/`is_valid_phase` keep working | Task 3.1 (delegation shim) |
| `keel.api` exports `Lifecycle`, `LifecycleState`, `load_lifecycle`, `iter_lifecycles`, `LifecycleNotFoundError` | Task 3.2 |
| README + CONTRIBUTING updates | Task 7.1 |

**Placeholder scan**: each step contains real test code, real implementation snippets, and exact commit commands. No "TBD" / "TODO" / "fill in details" remain.

**Type consistency**: `Lifecycle.successors(current: str) -> list[str]` is used identically in Tasks 1.1, 5.1, 6.3 (show), and 6.4 (validate). `LifecycleNotFoundError` raised from `load_lifecycle()` (Task 2.2) and caught in Task 4.2 (`new`) and Task 6.3 (`show`). Field `lifecycle: str = "default"` on `ProjectMeta` (Task 4.1) consumed by `cmd_new` (Task 4.2) and the phase command (Task 5.1).

**Out of scope (per spec):** Jira workflow import, plugin-shipped lifecycles via `keel.lifecycles` entry point, transition guards/actions in TOML, named transitions, lifecycle migration tool. None of these are in any task — correct.

---

## Execution Handoff

Plan saved to `keel/design/plans/2026-05-01-plan-7-customizable-lifecycles.md`.

Recommended: **subagent-driven execution** (matches Plans 5/5.1/5.2/5.3/5.4/5.5/6 in this repo). Tasks are mostly mechanical TDD with clear inputs/outputs.
