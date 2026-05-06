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
Both wheels stay on 0.0.x: `keel-cli` 0.0.2 → 0.0.3 and `keel-jira` 0.0.1 → 0.0.2
(pre-1.0 every release is "in development"; staying on 0.0.x signals "still
freely changing things, no compatibility promises yet").

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
