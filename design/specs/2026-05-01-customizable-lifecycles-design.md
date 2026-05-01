# Design: customizable phase lifecycles

**Status:** approved (brainstorming, 2026-05-01).
**Successor:** an implementation plan written via `superpowers:writing-plans`.

## Goal

Replace the hardcoded `PHASES = ["scoping", "designing", "poc", "implementing",
"shipping", "done"]` with a finite-state-machine model so users can define
their own phase lifecycles per project type. Workflows like
"needs-triage → in-doc-review → ready-for-development → in-code-review →
awaiting-public-preview → awaiting-ga → done" must be expressible without
modifying keel itself.

## Non-goals (v1)

- **Jira workflow import.** A `keel lifecycle import-from-jira` command would
  need a Jira plugin and is out of scope until one exists.
- **Plugin-shipped lifecycles** (`keel.lifecycles` entry-point group). Possible
  in v2 once an external plugin author needs it.
- **Transition guards or actions inside the lifecycle TOML.** The existing
  `keel.phase_preflights` and `keel.phase_transitions` entry-points already
  cover those concerns at the Python level. Adding inline DSL fields would be
  duplicate machinery.
- **Named transitions** (e.g., `keel phase reject`). v1 uses the target state
  name (`keel phase <target>`); transition names are easy to add later if
  needed.
- **Lifecycle migration** (`keel lifecycle migrate <project> --to <new>
  --map <old-state>=<new-state>`). Non-trivial and best deferred until at least
  one user actually wants to switch a live project's lifecycle.

## Lifecycle schema

Custom lifecycles live as TOML files. Example —
`~/projects/.keel/lifecycles/api-champions.toml`:

```toml
name = "api-champions"
description = "API champion workflow: triage → review → development → release."
initial = "needs-triage"
terminal = ["done", "cancelled"]

[states.needs-triage]
description = "Initial intake; requirements being clarified."

[states.in-doc-review]
description = "OpenAPI / Confluence doc under review."

[states.ready-for-development]
description = "Doc approved; coding can begin."

[states.in-code-review]
description = "Code under PR review."

[states.awaiting-public-preview]
description = "Code merged; awaiting public-preview release."

[states.awaiting-ga]
description = "In public preview; awaiting GA milestone."

[states.done]
description = "Released to GA."

[states.cancelled]
description = "Project cancelled."

[transitions]
needs-triage = ["in-doc-review"]
in-doc-review = ["ready-for-development", "needs-triage"]
ready-for-development = ["in-code-review"]
in-code-review = ["awaiting-public-preview", "ready-for-development"]
awaiting-public-preview = ["awaiting-ga"]
awaiting-ga = ["done"]
# Implicit: any state → "cancelled" (matches keel's existing behavior).
# Opt out per state with `cancellable = false`.
```

### Schema rules

- `name` (required, string): identifier used in `project.toml` and on the CLI.
  Must match the filename stem.
- `description` (optional, string): human-readable summary.
- `initial` (required, string): starting state for new projects. Must appear in
  `[states]`.
- `terminal` (required, list[string]): one or more states marking project
  completion. Must all appear in `[states]`. Conventionally includes `done`
  and `cancelled`. If `cancelled` is in `[states]`, it should be in `terminal`.
- `[states.<name>]` (one or more): each declares an FSM node. Fields:
  - `description` (optional).
  - `cancellable` (optional, bool, default `true`): controls whether the
    implicit `<state> → cancelled` transition is offered.
- `[transitions]` (table of name → list[name]): explicit forward and backward
  edges. If a `cancelled` state exists in `[states]`, an implicit
  `<state> → cancelled` transition is added for every state where
  `cancellable = true` (the default). Lifecycles that don't declare a
  `cancelled` state get no implicit cancellation transition — by design, so
  users can model workflows where cancellation isn't a thing.

### Validation

A lifecycle is valid when:

1. `name` matches the filename stem (lifecycle file → `<name>.toml`).
2. `initial` is in `[states]`.
3. Every entry in `terminal` is in `[states]`.
4. Every key in `[transitions]` is in `[states]`.
5. Every value in every transition list is in `[states]`.
6. The graph is reachable from `initial` (no orphan states).

`keel lifecycle validate <path>` runs these checks offline.

## Lookup precedence

When keel needs to resolve a lifecycle name, it searches in this order and
returns the first match:

1. **Project manifest:** `[project] lifecycle = "<name>"` in `project.toml`.
   Default value: `"default"` if the field is absent.
2. **User library:** `~/projects/.keel/lifecycles/<name>.toml`.
3. **Built-ins:** `keel/lifecycles/defaults/<name>.toml` shipped with the wheel.
   At minimum, `default.toml` exists here, mirroring the current 6 phases.
4. **Plugin packages** (deferred to v2): the `keel.lifecycles` entry-point
   group, looked up via `importlib.metadata.entry_points`.

A user library entry with the same name as a built-in **overrides** the
built-in, so users can customise the default lifecycle for their workspace
without forking keel.

If no lifecycle matches, `keel.api` raises `LifecycleNotFoundError` and
commands surface it via `out.fail(..., code=ErrorCode.NOT_FOUND)`.

## CLI surface

### Picking a lifecycle at project creation

`keel new <name> --lifecycle <id>` — adds `[project] lifecycle = "<id>"` to
the new project's `project.toml`. Default: `"default"` if `--lifecycle` is
omitted.

### Inspecting available lifecycles

`keel lifecycle list [--json]` — enumerates all reachable lifecycles
(built-ins + user library + plugins). Columns: name, description, source
(built-in / user / plugin).

`keel lifecycle show <name> [--json]` — prints the lifecycle's states + edges.
Human mode renders a Rich tree or table; JSON dumps the full parsed schema.

`keel lifecycle validate <path>` — lints a TOML file against the schema. Used
for both authored TOMLs in the user library and ad-hoc files.

`keel lifecycle init <name>` — scaffolds `~/projects/.keel/lifecycles/<name>.toml`
with placeholder states and transitions, ready for the user to edit.

### Phase navigation

These commands already exist; their behavior changes for non-default lifecycles:

- `keel phase --list-next [--json]` — returns the actual FSM successors of the
  current state. For branching lifecycles this can be a list of two or more.
- `keel phase <target>` — accepts any state name. Rejects if `<target>` is not
  in the transitions list from the current state. The implicit
  `<state> → cancelled` rule remains.
- `keel phase --next` — moves to the **first** successor in the FSM list. For
  unambiguous linear lifecycles this matches today's behavior. For branching
  lifecycles, the first list entry wins; users who want explicit choice use
  `keel phase <target>`.

## Code architecture

The implementation lives in a new `keel/lifecycles/` package (note plural; the
existing `keel/lifecycle.py` module stays for milestone/task state constants).

```
src/keel/
├── lifecycle.py              # UNCHANGED — milestone/task state constants
├── lifecycles/               # NEW — lifecycle FSM machinery
│   ├── __init__.py           # public re-exports
│   ├── models.py             # Lifecycle, LifecycleState Pydantic models
│   ├── loader.py             # load_lifecycle(name), iter_lifecycles(), lookup precedence
│   └── defaults/
│       ├── __init__.py       # makes the directory shippable
│       └── default.toml      # the current 6 phases as TOML
└── commands/
    └── lifecycle/            # NEW — keel lifecycle ... subgroup
        ├── __init__.py
        ├── list.py
        ├── show.py
        ├── validate.py
        └── init.py
```

### Pydantic models (sketch)

```python
# src/keel/lifecycles/models.py
class LifecycleState(BaseModel):
    description: str = ""
    cancellable: bool = True


class Lifecycle(BaseModel):
    name: str
    description: str = ""
    initial: str
    terminal: list[str]
    states: dict[str, LifecycleState]
    transitions: dict[str, list[str]] = Field(default_factory=dict)

    def successors(self, current: str) -> list[str]:
        """Allowed next states from `current`, including implicit cancelled."""
        ...

    def is_terminal(self, state: str) -> bool:
        ...
```

### Loader (sketch)

```python
# src/keel/lifecycles/loader.py
def load_lifecycle(name: str) -> Lifecycle:
    """Resolve a lifecycle by name through the precedence chain."""
    for path in _candidate_paths(name):
        if path.is_file():
            return _load_from_path(path)
    raise LifecycleNotFoundError(name)


def iter_lifecycles() -> list[Lifecycle]:
    """Return all reachable lifecycles, deduplicated by name (precedence wins)."""
    ...
```

### Backward compatibility

`keel.lifecycle` keeps its existing public signatures by delegating to the new
loader for the `"default"` lifecycle:

- `PHASES` (was `list[str]`): becomes a tuple/list derived from
  `load_lifecycle("default").states`. Order preserved.
- `DEFAULT_PHASE`: `load_lifecycle("default").initial`.
- `next_phase(current)`: returns the first successor in the default lifecycle's
  transitions; `None` if `current` is terminal or unknown.
- `is_valid_phase(name)`: `name in load_lifecycle("default").states`.

Existing projects without a `[project] lifecycle` field continue working
unchanged because the default lifecycle TOML mirrors the current 6 phases
exactly. No migration step is needed.

### Public API additions in `keel.api`

- `Lifecycle`, `LifecycleState` (Pydantic models).
- `load_lifecycle`, `iter_lifecycles` (loader functions).
- `LifecycleNotFoundError` (exception).

### Manifest model change

`ProjectManifest.project` (Pydantic) gains an optional `lifecycle: str = "default"`
field. Existing TOMLs without the field round-trip cleanly (the default fills
in). The `keel manifest validate` command (Plan 6) inherits the change for
free via Pydantic.

## Migration path

- **Existing projects:** unchanged. Their `project.toml` lacks
  `[project] lifecycle =`, which Pydantic fills with `"default"`. The default
  lifecycle's TOML produces the same `PHASES` list as before.
- **New projects:** `keel new <name>` writes
  `[project] lifecycle = "default"` explicitly so the file is self-documenting.
- **Switching a live project's lifecycle:** out of scope for v1. Users who
  need it can edit `project.toml` by hand and reset `.phase` — `keel
  manifest validate` and `keel lifecycle show` together let them check the
  result.

## Testing strategy

- **Unit:** Pydantic round-trip for `Lifecycle`. Loader precedence with
  monkeypatched library/plugin paths. Validation rules each have a positive
  and negative test.
- **CLI:** `keel lifecycle list/show/validate/init` each get 2-3 tests
  (success + error case).
- **End-to-end:** create a project with a custom lifecycle in the user
  library, advance phases through it, verify `keel phase --list-next` reports
  branching options, verify the existing preflight framework still fires for
  the default lifecycle and is silent for custom ones (since built-in
  preflights only match default phase names).
- **Backward compat:** an existing pre-v1 project (no `lifecycle` field)
  loads cleanly and behaves like before.

## Open questions and future work

- **Plugin-shipped lifecycles**: a `keel.lifecycles` entry-point group + a
  loader path that scans entry points. Defer until a real consumer surfaces.
- **Lifecycle migration tool**: `keel lifecycle migrate <project>
  --to <new> --map <old>=<new>` for switching a live project's lifecycle.
  Non-trivial; defer.
- **Transition names** (`keel phase reject` instead of `keel phase needs-triage`):
  pleasant ergonomics, but invites bikeshedding on the namespace. Wait for
  demand.
- **Per-lifecycle preflights declared inline**: rather than registering via
  the Python entry-point, embed a small predicate language in the TOML.
  Probably YAGNI — Python is more readable than a custom DSL for that scope.
- **Jira workflow import**: parse a Jira project's status mapping and emit
  a starter TOML. Belongs to whichever Jira plugin ships first.
