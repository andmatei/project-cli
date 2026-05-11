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
