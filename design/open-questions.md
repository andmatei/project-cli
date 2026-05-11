# Open contract questions

A parking lot for design questions that haven't been resolved yet. Move
items into `design/decisions/` (with rationale) once a call is made, or
delete them if they become moot. Date-stamp each entry so we can track
how long things have been open.

---

## 2026-05-05 — TOML contract questions raised after Plans 6/7 + first plugin

Surfaced during the post-publish review of `keel-cli` 0.0.2 + `keel-jira`
0.0.1. Pruned 2026-05-06 after Plan 8 shipped — items 3 and 6 were
resolved by T9.2 (CONTRIBUTING now documents the `[extensions]` selector
pattern).

### High value, low cost

1. **Schema versioning.** No manifest file (`project.toml`,
   `milestones.toml`, lifecycle TOMLs) declares its schema version. The
   first breaking change to any of them will silently misread existing
   files. Options: top-level `schema = 1`, or rely on Pydantic's
   `extra="forbid"` + clear error messages, or semver-the-wheel and
   document migrations.

2. **`ticket_id` is a single string.** Assumes one ticketing provider per
   entity. Renaming to `tickets = { jira = "...", github = "..." }` is
   cheaper now than later. Plan 8's spec deferred multi-provider, but
   the field shape is still the deciding factor.

3. **State-name convention across lifecycles.** Default uses lowercase
   single words (`scoping`, `designing`); examples used kebab-case
   (`needs-triage`, `in-doc-review`). Document one rule.

### Worth discussing

4. **`Task.branch` assumes git.** Research / non-code projects have no
   branches. Could move into `extensions.code` to keep `Task` provider-
   agnostic, or rename to a neutral `work_ref` with semantics defined per
   lifecycle.

5. **`Milestone.fan_out` is unvalidated.** Nothing checks that named
   deliverables have a matching `parent = m.id` milestone. `keel validate`
   could enforce.

6. **`lifecycle = "default"` implicit default.** Plan 8 made this more
   load-bearing (the resolved lifecycle is now snapshotted into
   `.keel/lifecycle.lock.toml` at `keel new` time). If `default` ever
   changes meaning, projects without an explicit field silently drift on
   *new* projects but lock-file-consistent on existing ones. Question is
   whether new-project behavior should require an explicit pick.

### Defer

7. **`description = ""` proliferation.** Cosmetic; switch to `Optional`
   later if it grates.

8. **`created` is date-only.** Loses timezone/time. Probably fine for
   humans; revisit only if audit needs surface.

---

## 2026-05-11 — Feature ideas surfaced during Plan 9

### Tags for projects and deliverables

User wants to add tags to projects (and deliverables) for categorization
and filtering on `keel list` / `keel deliverable list`. Likely fits as:
- `tags: list[str]` field on `ProjectMeta` (TOML: `tags = ["api", "research"]`)
- `--tag <name>` filter on `keel list` (repeatable, AND semantics)
- Reasonable defaults: empty list, validator forbids whitespace/special chars
- Open Qs: hierarchical tags? `keel tag add/rm` management commands? colors
  for terminal rendering?

Worth its own brainstorm + plan after Plan 9 ships. Small surface, no
breaking changes expected — `tags` defaults to `[]`, existing projects
work unchanged.

---

(Add more sections below as new questions surface.)
