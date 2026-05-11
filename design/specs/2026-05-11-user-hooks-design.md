---
date: 2026-05-11
title: User hooks framework + phase-event consolidation
status: draft
---

# User hooks framework + phase-event consolidation

## Summary

Introduce a unified hook system for keel CLI commands. Commands declare
hookability via a decorator; a central dispatcher fans events out to user
scripts (in `.keel/hooks/`), plugin entry-points, and in-tree subscribers.
The existing `keel.phase_preflights` and `keel.phase_transitions`
entry-point groups (Plan 6) are folded into the same dispatcher with
bridge adapters for backward compatibility.

Goal: one consistent way to react to keel events — whether you're a user
writing a Slack notifier, a plugin author shipping reusable rules, or
keel itself shipping built-in phase checks.

## Motivation

After Plan 8 the plugin surface has converged on a clean shape (typed
TicketProvider, per-plugin templates, `.keel/` for state). Three gaps
remain for personal automation and cross-plugin coordination:

1. **Users have no way to react to keel events.** "Create a Linear ticket
   when I run `keel new`," "post to Slack when I move to `implementing`,"
   "back up the project when I `archive`" — all require keel-aware Python
   plugin packaging today. Git-style executable hooks are dramatically
   lower-friction.

2. **Phase preflights and transitions are obscure parallel APIs.** Two
   separate entry-point groups (`keel.phase_preflights`,
   `keel.phase_transitions`), each with its own loader, call signature,
   and registration mechanism. A user looking for "I want to do X when
   phase changes" has to learn both. Unifying them on one dispatcher
   simplifies the mental model.

3. **No bus for future cross-plugin coordination.** keel-ai (future) needs
   a file-change event to re-index. Other plugins may want to react to
   project lifecycle. Adding bus infrastructure now lets future plugins
   subscribe without each one inventing its own observer pattern.

This spec covers (1) and (2) for v0. (3) is enabled but not consumed —
file events are deferred to a separate plan, and keel-ai will plug into
the same dispatcher when it lands.

## Architecture

### Central dispatcher

A new module `keel.hooks` owns event dispatch. Single source of truth for
all event firing.

```python
# keel/hooks/__init__.py (sketch)

@dataclass(frozen=True)
class HookEvent:
    name: str                    # e.g., "new", "phase", "deliverable-add"
    phase: Literal["pre", "post"]
    project: str | None
    deliverable: str | None
    payload: dict[str, Any]      # event-specific structured data
    positional_args: tuple[str, ...]  # for git-style hook scripts

class HookAborted(RuntimeError):
    """Raised when a pre-hook exits non-zero or a subscriber raises."""

def dispatch(event: HookEvent, *, out: Output) -> None:
    """Fan the event out to all subscribers.

    Pre-events: ANY exception raised by a subscriber (HookAborted or
    otherwise) propagates and aborts the command. A buggy preflight is
    treated the same as one that intentionally blocks — both stop the
    transition. This keeps the dispatcher simple and the failure mode
    obvious.

    Post-events: all exceptions are caught and emitted via out.warn().
    The command has already succeeded; post-hook failures are advisory.
    """
    ...
```

Subscribers come from three sources, fired in this order per event:

1. **In-tree subscribers** registered via `@hooks.subscribe("pre-phase")`
   (built-in preflights live here after migration).
2. **Plugin entry-point subscribers** via the new `keel.event_listeners`
   entry-point group.
3. **User scripts** in `<workspace>/.keel/hooks/<event>` then
   `<project>/.keel/hooks/<event>`.

Order matters: in-tree first (deterministic, ships with keel), plugins
next (additive), user scripts last (most likely to do side effects).

### Command-side API

Commands opt in via a decorator + context manager:

```python
# keel/commands/new.py (after migration)

@hookable("new")  # decorator marks the command as having pre/post hooks
def cmd_new(ctx, name, description, ...):
    slug = slugify(name)
    # ... validation ...

    with hook_event(
        "new",
        project=slug,
        positional_args=(slug,),
        payload={"description": description, "lifecycle": lifecycle, ...},
    ) as event:
        # pre-new fires when entering the with block
        # body does the actual work
        _scaffold_unit(...)
        # post-new fires when exiting cleanly (skipped on exception)
```

The decorator records `cmd_new` in the command registry (useful for
`keel plugin list --hooks`). The context manager wraps the actual work
and fires `pre-<event>` on entry, `post-<event>` on clean exit. Aborts
in pre-hooks raise `HookAborted` which propagates out of `cmd_new`.

**Default policy:** commands without `@hookable(...)` fire no events.
Authors opt in explicitly. This avoids accidentally exposing internal
commands (`completion`, `plugin`) and forces conscious payload design.

### Plugin subscriber API

A new entry-point group `keel.event_listeners` lets plugins subscribe:

```toml
# plugins/my-plugin/pyproject.toml

[project.entry-points."keel.event_listeners"]
on_new = "my_plugin.listeners:on_project_created"
on_phase = "my_plugin.listeners:on_phase_change"
```

```python
# my_plugin/listeners.py

from keel.hooks import HookEvent, HookAborted, subscribes_to

@subscribes_to("post-new")
def on_project_created(event: HookEvent, *, out) -> None:
    # event.project, event.payload available
    ...

@subscribes_to("pre-phase")
def on_phase_change(event: HookEvent, *, out) -> None:
    if event.payload["to"] == "done":
        if has_open_tickets(event.project):
            raise HookAborted("cannot move to 'done' with open tickets")
```

The `@subscribes_to` decorator binds the function to an event name. The
entry-point loader walks each plugin and registers its listeners.

## Hook event surface (v0)

Events fired in v0:

| Command | Event name | Pre fires | Post fires | Pre payload | Post payload |
|---|---|:---:|:---:|---|---|
| `keel new` | `new` | ✓ | ✓ | `{description, lifecycle}` | + `{path}` |
| `keel phase <to>` | `phase` | ✓ | ✓ | `{from, to}` | same |
| `keel deliverable add` | `deliverable-add` | ✓ | ✓ | `{description, lifecycle}` | + `{path}` |
| `keel decision new` | `decision-new` | ✓ | ✓ | `{slug, title, supersedes}` | + `{path}` |
| `keel archive` | `archive` | ✓ | ✓ | `{}` | + `{archived_path}` |
| `keel restore` | `restore` | — | ✓ | — | `{path}` |
| `keel rename` | `rename` | — | ✓ | — | `{old_name, new_name}` |

Deferred to v0.1: milestone/task/code/migration command events. They're
more granular and the personal-automation value is lower until heavy use
develops.

## Protocol

User scripts receive the event via three channels (git-style):

| Channel | Contents |
|---|---|
| Positional args | 1–3 high-value identifiers per event |
| Env vars | `KEEL_EVENT`, `KEEL_PROJECT`, `KEEL_DELIVERABLE`, per-event extras (`KEEL_PHASE_FROM`, `KEEL_DECISION_SLUG`, etc.) |
| stdin | JSON dump of the full `HookEvent.payload` (always present; consumers may ignore) |

### Positional args by event

| Event script | Args |
|---|---|
| `pre-new` / `post-new` | `<project_slug>` |
| `pre-phase` / `post-phase` | `<from_phase> <to_phase>` |
| `pre-deliverable-add` / `post-deliverable-add` | `<deliverable_slug>` |
| `pre-decision-new` / `post-decision-new` | `<decision_slug>` |
| `pre-archive` / `post-archive` | `<project_name>` |
| `post-restore` | `<project_name>` |
| `post-rename` | `<old_name> <new_name>` |

Stable, additive: new fields go through env vars or stdin JSON; positional
args never reorder.

### Env var convention

| Var | Always set? | Contents |
|---|:---:|---|
| `KEEL_EVENT` | ✓ | event name with phase prefix (e.g. `pre-phase`, `post-new`) |
| `KEEL_PROJECT` | ✓ when in scope | project slug |
| `KEEL_DELIVERABLE` | when in scope | deliverable slug |
| `KEEL_<EVENT>_<FIELD>` | per event | event-specific (e.g. `KEEL_PHASE_FROM`, `KEEL_PHASE_TO`) |
| `KEEL_HOOK_LAYER` | ✓ | `workspace` or `project` (so a single script can branch) |

## Pre-hook semantics

- Non-zero exit on a user script → command aborts. Hook's stderr surfaces
  in the keel error message.
- `HookAborted` raised by an in-tree or plugin subscriber → same outcome.
- `--no-verify` flag on the failing command bypasses **all pre-hooks**
  (user scripts + plugin subscribers + in-tree subscribers). Useful for
  emergencies; warned about prominently.
- Post-hooks **always** run. Failures in post-hooks emit `out.warn(...)`
  but never abort. The command has already completed.

## Hook discovery

| Layer | Location | Order |
|---|---|---|
| Workspace | `~/projects/.keel/hooks/<event>` | runs first |
| Project | `<project>/.keel/hooks/<event>` | runs after workspace |

Single executable per event in v0 (matches git). The `.d/<NN>-name`
multi-file pattern is deferred — easy to add later, useful only when
users compose many automations.

A hook script that's not executable is **skipped silently** (matches git;
avoids friction when checking out scripts cross-platform).

`.keel/hooks/` is created on demand: `keel hooks init` (workspace or
project) scaffolds the directory with a README pointing at the docs.

## Phase-event consolidation

The new dispatcher replaces both legacy entry-point groups:

| Legacy | New |
|---|---|
| `keel.phase_preflights` entry-point + `PhasePreflight.check()` shape | `keel.event_listeners` subscribers on `pre-phase` (raise `HookAborted` to block) |
| `keel.phase_transitions` entry-point + `hook(scope, from, to)` | `keel.event_listeners` subscribers on `post-phase` |
| Built-in preflights in `keel.preflights.builtin` (`_ScopeEditedPreflight`, `_DesignEditedPreflight`) | Refactored to in-tree subscribers via `@subscribes_to("pre-phase")` |

### Bridge adapters

Existing out-of-tree plugins that ship `keel.phase_preflights` or
`keel.phase_transitions` entry-points continue to work. A bridge adapter
loads the legacy entry-points and registers them as
`pre-phase`/`post-phase` subscribers on the new dispatcher:

```python
# keel/hooks/_bridges.py (sketch)

def _bridge_phase_preflights() -> None:
    """Load legacy keel.phase_preflights and register as pre-phase subscribers."""
    for ep in entry_points(group="keel.phase_preflights"):
        getter = ep.load()
        for preflight in getter():
            _adapt(preflight)  # wraps .check() to a pre-phase subscriber

def _adapt(preflight: PhasePreflight) -> EventListener:
    @subscribes_to("pre-phase")
    def _adapted(event: HookEvent, *, out):
        result = preflight.check(
            scope=Scope(project=event.project, deliverable=event.deliverable),
            from_phase=event.payload["from"],
            to_phase=event.payload["to"],
        )
        for warning in result.warnings:
            out.warn(f"[{preflight.name}] {warning}")
        if result.blocked:
            raise HookAborted(f"[{preflight.name}] {result.message}")
    return _adapted
```

### Deprecation schedule

| Version | Status |
|---|---|
| 0.0.4 (this plan) | New dispatcher ships. Legacy groups load via bridges. `DeprecationWarning` on legacy entry-point discovery. |
| 0.0.5 | Update CONTRIBUTING + docs to point at new API. |
| Future 0.0.x | Remove `keel.phase_preflights` and `keel.phase_transitions` entry-point groups. Bridge code deleted. |

## Migration guide

### For plugin authors using `keel.phase_preflights`

**Before:**
```toml
[project.entry-points."keel.phase_preflights"]
my_preflights = "my_pkg.preflights:get_preflights"
```

```python
# my_pkg/preflights.py

from keel.preflights.base import PhasePreflight, PreflightResult

class _RequireMilestonesPreflight:
    name = "milestones-defined"

    def check(self, scope, from_phase, to_phase) -> PreflightResult:
        if to_phase != "implementing":
            return PreflightResult()
        manifest = load_milestones_manifest(scope.milestones_manifest_path)
        if not manifest.milestones:
            return PreflightResult(
                warnings=["no milestones defined; consider adding before implementing"]
            )
        return PreflightResult()

def get_preflights():
    return [_RequireMilestonesPreflight()]
```

**After:**
```toml
[project.entry-points."keel.event_listeners"]
require_milestones = "my_pkg.hooks:require_milestones"
```

```python
# my_pkg/hooks.py

from keel.hooks import HookEvent, HookAborted, subscribes_to
from keel.api import load_milestones_manifest, Scope

@subscribes_to("pre-phase")
def require_milestones(event: HookEvent, *, out) -> None:
    if event.payload["to"] != "implementing":
        return
    scope = Scope(project=event.project, deliverable=event.deliverable)
    manifest = load_milestones_manifest(scope.milestones_manifest_path)
    if not manifest.milestones:
        out.warn("no milestones defined; consider adding before implementing")
```

To block instead of warn, raise `HookAborted("reason")` instead of calling
`out.warn(...)`.

### For plugin authors using `keel.phase_transitions`

**Before:**
```toml
[project.entry-points."keel.phase_transitions"]
notify = "my_pkg.hooks:on_transition"
```

```python
def on_transition(scope, from_phase, to_phase):
    send_slack(f"{scope.project}: {from_phase} → {to_phase}")
```

**After:**
```toml
[project.entry-points."keel.event_listeners"]
notify = "my_pkg.hooks:on_transition"
```

```python
@subscribes_to("post-phase")
def on_transition(event: HookEvent, *, out) -> None:
    send_slack(
        f"{event.project}: {event.payload['from']} → {event.payload['to']}"
    )
```

### For users wanting personal automation

Write an executable script and drop it in `~/projects/.keel/hooks/`. The
script can be in any language — keel just executes it.

**Example: post a Slack message when a phase changes**

```bash
#!/usr/bin/env bash
# ~/projects/.keel/hooks/post-phase
# Args: <from_phase> <to_phase>
FROM=$1; TO=$2
curl -s -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d "{\"text\":\"$KEEL_PROJECT: $FROM → $TO\"}"
```

```bash
chmod +x ~/projects/.keel/hooks/post-phase
```

**Example: block `keel phase done` if there are open Jira tickets**

```bash
#!/usr/bin/env bash
# ~/projects/.keel/hooks/pre-phase
# Args: <from_phase> <to_phase>
[[ "$2" != "done" ]] && exit 0
open_tickets=$(curl -s "$JIRA_API/search?jql=project=$KEEL_PROJECT+AND+status!=Done" | jq '.total')
if (( open_tickets > 0 )); then
    echo "error: $open_tickets open tickets in $KEEL_PROJECT" >&2
    exit 1
fi
```

**Example: read the full payload via stdin**

```python
#!/usr/bin/env python3
# ~/projects/.keel/hooks/post-decision-new
import json, sys
event = json.load(sys.stdin)
# event = {"name": "decision-new", "phase": "post", "project": "...",
#          "deliverable": None, "payload": {"slug": "...", "title": "...", "path": "..."}}
print(f"Decision recorded: {event['payload']['title']}")
```

### Discovering hookable commands

```bash
keel hooks list           # all available events
keel hooks list --command new  # events fired by a specific command
keel hooks list --plugin       # subscribers registered by plugins
```

## Out of scope for v0

- **Windows support for executable detection.** v0 uses `os.access(p, os.X_OK)`
  which is Unix-specific. keel is currently Unix-oriented (git worktrees,
  uv tool install workflows); Windows support is a separate concern.
- **File-level events.** Re-fire on every write to `scope.md`, `design.md`,
  `decisions/*`, etc. Will ship as a separate plugin (likely
  `keel-watch`) using `watchdog` or `watchfiles`. Decouples the
  platform-specific watching machinery from keel-cli core.
- **`.d/` hook-directory pattern.** Multi-file per event. Easy to add
  later when single-file becomes cramped.
- **Async/parallel execution.** Subscribers run sequentially in
  documented order. No `asyncio` plumbing in v0.
- **Hook timeouts.** A hung hook hangs the command. Defer until someone
  reports it.
- **Milestone/task/code/migration command events.** Lower
  personal-automation value; add in v0.1 when usage patterns clarify.

## Testing strategy

| Area | Tests |
|---|---|
| Dispatcher | unit tests with fake subscribers — ordering (in-tree → plugin → user-script), exception propagation in pre vs post, payload routing |
| User-script integration | `tmp_path` writes hook scripts; runs command; asserts hook fired, env vars seen, args correct, stdin parsed, exit code respected |
| Plugin entry-point loading | a fake plugin registers via test fixture; verifies `@subscribes_to` resolves and subscriber receives `HookEvent` |
| Legacy bridge | a fake legacy `phase_preflights` plugin → verifies bridge adapts and fires on `pre-phase`; `DeprecationWarning` emitted |
| `--no-verify` | pre-hook that would block; with the flag, command succeeds; without, command exits 1 |
| Hook discovery layering | workspace hook + project hook both present; both fire in the right order |
| Per-event smoke | one integration test per event in v0 surface (7 events × {pre,post} where applicable ≈ 12 tests) |

## Implementation notes

- The decorator `@hookable("event-name")` records the command in a
  module-level registry, used by `keel hooks list` for introspection
  (showing which commands fire which events). It doesn't wrap the
  function — the actual dispatch happens inside the function body via
  the `hook_event` context manager.
- `hook_event` is a context manager so that `with hook_event(...) as e:`
  reads naturally and post-hooks only fire on clean exit. Exceptions
  inside the body skip post-hooks (the command failed; nothing to react
  to).
- User-script hooks resolve via `os.access(path, os.X_OK)` — non-executable
  files are skipped silently. Matches git.
- Workspace `.keel/hooks/` is opt-in: keel doesn't create it on first run.
  `keel hooks init` (workspace mode) scaffolds it with a README.
- The legacy bridges install on first import of `keel.hooks` and emit
  `DeprecationWarning` once per legacy entry-point group (not per
  subscriber — would be noisy).

## Open questions (resolve during implementation)

None currently. All major design points are settled.
