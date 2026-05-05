# Open contract questions

A parking lot for design questions that haven't been resolved yet. Move
items into `design/decisions/` (with rationale) once a call is made, or
delete them if they become moot. Date-stamp each entry so we can track
how long things have been open.

---

## 2026-05-05 — TOML contract questions raised after Plans 6/7 + first plugin

Surfaced during the post-publish review of `keel-cli` 0.0.2 + `keel-jira`
0.0.1. Some of these may dissolve after a fuller "what is keel's data
model trying to express" brainstorm; recording here so they're not lost.

### High value, low cost

1. **Schema versioning.** No manifest file (`project.toml`,
   `deliverable.toml`, `milestones.toml`, lifecycle TOMLs) declares its
   schema version. The first breaking change to any of them will silently
   misread existing files. Options: top-level `schema = 1`, or rely on
   Pydantic's `extra="forbid"` + clear error messages, or semver-the-wheel
   and document migrations.

2. **`ticket_id` is a single string.** Assumes one ticketing provider per
   entity. Renaming to `tickets = { jira = "...", github = "..." }` is
   cheaper now than later.

3. **`[extensions]` conventions are under-documented.** Every plugin
   author has to read the keel-jira source to learn the namespacing rules.
   Short spec section under CONTRIBUTING.md or a public doc page.

4. **State-name convention across lifecycles.** Default uses lowercase
   single words (`scoping`, `designing`); examples used kebab-case
   (`needs-triage`, `in-doc-review`). Document one rule.

### Worth discussing

5. **`Task.branch` assumes git.** Research / non-code projects have no
   branches. Could move into `extensions.code` to keep `Task` provider-
   agnostic, or rename to a neutral `work_ref` with semantics defined per
   lifecycle.

6. **`[extensions.ticketing]` has a hidden selector pattern.** It's the
   only extension with `provider = "<name>"` + nested per-provider config.
   Either document the pattern or rename to `[ticketing]` to make it less
   weird.

7. **`Milestone.fan_out` is unvalidated.** Nothing checks that named
   deliverables have a matching `parent = m.id` milestone. `keel validate`
   could enforce.

### Defer

8. **`description = ""` proliferation.** Cosmetic; switch to `Optional`
   later if it grates.

9. **`created` is date-only.** Loses timezone/time. Probably fine for
   humans; revisit only if audit needs surface.

10. **`lifecycle = "default"` implicit default.** If `default` ever
    changes meaning, projects without an explicit field silently drift.
    Either require the field (with a migration helper) or freeze the
    name `default`.

---

(Add more sections below as new questions surface.)
