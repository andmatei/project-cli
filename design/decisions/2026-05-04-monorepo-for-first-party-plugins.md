---
date: 2026-05-04
title: Monorepo for first-party plugins, with documented migration triggers to separate repos
status: accepted
---

# Monorepo for first-party plugins, with documented migration triggers to separate repos

## Question

The plan-5 pure-plugin decision committed `keel-cli` to ship without bundled
providers — keel-jira and any future first-party plugins are independently
versioned, independently published wheels. That decision said nothing about
**source layout**: should each first-party plugin live in its own GitHub repo,
or co-locate under one monorepo?

## Options explored

### Option A — separate repos

`andmatei/keel` for keel-cli; `andmatei/keel-jira` and any future
first-party plugins as separate GitHub repos. Each has its own CI, issue
tracker, release pipeline. Pattern: pytest, mkdocs, sphinx, datasette.

### Option B — monorepo, Airflow-style

One repo at `andmatei/keel`. Layout:

```
keel/
├── src/keel/             # core
├── plugins/
│   └── jira/             # first plugin; ships as keel-jira on PyPI
└── pyproject.toml        # workspace root
```

Each plugin keeps its own `pyproject.toml` and ships as its own PyPI wheel.
Pattern: Apache Airflow, Prefect 2.x (post-2024), OpenTelemetry-contrib.

## Evidence reviewed

Four review agents were dispatched along distinct lenses (architecture,
developer experience, ecosystem signaling, real-world evidence). The verdict
split 2–2:

- **Architecture & DX (both B, high confidence):** the existing local
  `[tool.uv.sources]` cross-pin between `~/projects/keel` and
  `~/projects/keel-jira` is already a de-facto monorepo with extra steps.
  Cross-cutting changes during plan-5/6/7 protocol churn need to be atomic.
  One CI catches integration regressions; solo-maintainer overhead halves.
- **Ecosystem & real-world evidence (both A, high / medium-high confidence):**
  pytest's 1,745-plugin ecosystem proves separate-repo zero-friction
  contribution produces vibrant ecosystems. Airflow's monorepo works because
  of ASF backing — not transferable. Prefect's A→B migration happened at
  ~10 plugins, not 1.

## Conclusion

**Option B (monorepo) for now**, with explicit triggers to migrate to A.

The B-voters' argument is concrete and immediate: at 1 plugin, with the
plugin protocol still maturing, A's coordination overhead is daily and real.
The A-voters' argument is conditional on a community-plugin ecosystem that
may or may not materialize. The asymmetric risk:

- B with 1 plugin and a maturing protocol: small annoyance for hypothetical
  future external contributors.
- A with 1 plugin and a maturing protocol: significant ongoing release-dance
  cost on every protocol change.

Migration in either direction is well-precedented. Prefect 2.x consolidated
several integration repos into a monorepo; dbt-labs split `dbt-adapters` out
of `dbt-core`. Neither was a one-way door.

## Migration triggers (B → A)

Revisit this decision and migrate `plugins/<name>/` directories out into
separate GitHub repos when **any** of the following becomes true:

1. **Plugin count.** Five or more first-party plugins live under `plugins/`.
2. **External adoption.** A community-authored plugin (`someone/keel-foo`)
   reaches notable traction (~100+ GitHub stars or weekly PyPI downloads
   matching first-party plugin levels).
3. **Protocol stability.** The plugin entry-point contract has had no
   breaking changes for 6 consecutive months — at which point the
   refactor-friction argument for B mostly dissolves.
4. **Maintainership divergence.** A first-party plugin attracts an outside
   maintainer who should have commit access to that plugin only, not core.

If any trigger fires, a follow-up decision file documents the migration plan
(per-plugin, in priority order).

## Consequences

- `~/projects/keel-jira/` (the local-only sibling repo) is folded into
  `~/projects/keel/plugins/jira/`. The local `keel-jira` git history (one
  commit, `v0.1.0` tag) is dropped — nothing was published.
- `keel/pyproject.toml` declares a uv workspace whose members are
  `plugins/*`; the `[tool.uv.sources] keel-jira = ...` cross-pin disappears.
- `plugins/jira/pyproject.toml` retains its identity (own version, own
  dependencies, own entry-point declaration). The `[tool.uv.sources] keel-cli
  = ...` cross-pin disappears because workspace members resolve each other
  automatically.
- CI runs `pytest` once at the workspace root, walking all members.
- The README adds a "Where plugins live" section pointing at `plugins/`,
  plus an "Authoring an external plugin" section that explicitly invites
  third-party plugins to live in their own repos.
- This file is the durable record of the trigger conditions; check it
  whenever someone proposes adding a new plugin.
