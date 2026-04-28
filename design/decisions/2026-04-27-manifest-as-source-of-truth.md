---
date: 2026-04-27
title: TOML manifest as source of truth for code linkage
status: accepted
---

# TOML manifest as source of truth for code linkage

## Question

Today, the linkage between a project (or deliverable) and its source repos /
worktrees lives as free-text in `CLAUDE.md`'s "## Code" and "## Deliverables"
sections. The current `add-deliverable` Bash subcommand mutates these sections
via `sed -i ''` regex replacements. Pain points:

- The text isn't machine-readable, so other tools can't reason about repo
  linkage.
- It's not portable — someone cloning `~/projects` can't reproduce the local
  state (worktrees, branch names, source repo paths) without manually parsing
  prose.
- Cross-file mutations via `sed` are fragile; if the parent CLAUDE.md drifts
  even slightly from the expected shape, the regex breaks silently or
  duplicates.
- There's no place to record additional structured info (branch prefixes,
  shared-worktree flag, suggested local paths).

What should the source of truth for code linkage be?

## Options explored

### Option A: TOML manifest per unit (chosen)

`design/project.toml` and `design/deliverable.toml`. Schema validated by
Pydantic on every read. CLAUDE.md's "## Code" and "## Deliverables" sections
are **generated** from the manifest, not hand-edited.

- **Pros**: portable (anyone cloning the workspace can reconstruct local
  state via `project code init`); structured (extensible — branch prefix,
  shared flag, local hints, future fields like milestones); diff-friendly
  (changes to repo linkage produce small, reviewable diffs); enables
  `code list/status/init/add/rm` commands; eliminates the `sed`
  fragility for the code-linkage parts of CLAUDE.md.
- **Cons**: introduces a new file format users must learn (mitigated — TOML
  is widely understood, native to `pyproject.toml`); slight duplication
  between manifest and CLAUDE.md (mitigated — CLAUDE.md is generated, never
  hand-edited for these sections).

### Option B: YAML manifest per unit

Same shape, different format. Rejected because YAML's whitespace traps and
spec ambiguity (`yes`/`no` parsing, etc.) make it less safe for hand-editing
than TOML, and we already need TOML for `pyproject.toml`.

### Option C: JSON manifest per unit

Rejected — no comments, less ergonomic for hand-editing.

### Option D: Keep CLAUDE.md text as source of truth, just AST-edit it instead of regex

- **Pros**: no new files; humans read CLAUDE.md, not a manifest.
- **Cons**: still not machine-portable in a structured way (someone parsing
  needs to walk the markdown AST); content schema is implicit, not validated;
  doesn't enable `code list/status/init` cleanly without re-deriving structure
  every time. AST-editing CLAUDE.md is still required for *human-narrative*
  sections (parent's `## Deliverables` list, sibling references), but the
  *code-linkage* sections benefit from being generated rather than hand-edited.

### Option E: Single workspace-level manifest

One file at `~/projects/manifest.toml` listing every project and deliverable.
Rejected — couples otherwise-independent projects, makes deliverable-level
edits expensive (rewrites a global file), and breaks the "deliverable is a
mini-project" principle.

## Conclusion

Adopt Option A: per-unit TOML manifests as source of truth for code linkage.
CLAUDE.md "## Code" and "## Deliverables" sections are generated from the
manifest. AST-aware editing handles the human-narrative cross-file mutations
(parent ↔ deliverable references, sibling-of-deliverable lists) — those are
not derived from the manifest.

## Consequences

- New required files: `design/project.toml` (per project),
  `design/deliverable.toml` (per deliverable).
- New command group: `project code {list, status, init, add, rm}` for
  manifest-driven worktree management.
- New command (one-shot): `project migrate` to populate manifests from
  existing CLAUDE.md text for projects that pre-date this rewrite.
- `validate` checks: TOML parses, schema matches, declared worktrees exist on
  disk, branches start with declared `branch_prefix`.
- Hand-editing CLAUDE.md "## Code" / "## Deliverables" no longer works — those
  get regenerated; the manifest is the place to make changes.
