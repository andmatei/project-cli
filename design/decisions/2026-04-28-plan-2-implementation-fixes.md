---
date: 2026-04-28
title: Plan 2 implementation fixes and forward debt update
status: accepted
---

# Plan 2 implementation fixes and forward debt update

Captures Plan 2's implementation-time fixes plus an updated view of the
forward-debt list from the Plan 1 fixes decision (which is now partially
stale).

## Implementation-time fixes (already committed during Plan 2 execution)

- **Test isolation for `make_project`** — the `make_project` fixture was
  extended to render `CLAUDE.md` and `design.md` via the templates so
  AST-edit tests had something to mutate. Was previously creating only
  `project.toml` and `.phase`. (Plan 2 commit history.)

## Critical bugs found in post-Plan-2 review and fixed in Plan 2.5

- **`deliverable rm --keep-code` silently destroyed the worktree dir.**
  Fixed in commit `ef730f0`. The unconditional `shutil.rmtree(deliv)` at the
  end of `cmd_rm` was rmtreeing the worktree the flag was meant to preserve;
  changed to `shutil.rmtree(deliv / "design")` then conditional rmdir of the
  parent dir.
- **`deliverable rename` broke worktree git linkage.** Fixed in `dd59b96`.
  Used `shutil.move` for the whole `deliv/` dir, breaking git's worktree
  registration; now uses `git_ops.move_worktree` for the `code/` subdir
  followed by `shutil.move` for the rest. Removed the unreliable
  `git worktree repair` recovery dance.
- **`decision new --supersedes <wrong-slug>` silently succeeded.** Fixed in
  `ed454fc`. Validation moved before file creation; on no match, exits 1
  with `code="not_found"`.

## Forward-debt items from Plan 1 fixes decision — status update

| Item from Plan 1 fixes | Status as of Plan 2.5 |
|---|---|
| `replace_section` blank-line stability | Resolved (Plan 2 commit `d04ad8e`). |
| `detect_scope` existence validation | Resolved — `resolve_scope_or_fail` added in Plan 2; `resolve_cli_scope` (CLI-flavored) added in Plan 2.5 (replaces 8 sites of duplicated boilerplate). |
| `Output.warn` test gap | Resolved in Plan 2. |
| `confirm_destructive` test gap | Resolved in Plan 2. |
| `_slugify` edge case test gap | Resolved in Plan 2; in Plan 2.5 the function moved to `keel/util.py` and the test was rewired. |
| `commands/` subpackage restructure | Done in Plan 2. |
| Multi-repo `Path.name` collision | Still deferred. Plan 3's `code add` is the natural place to add the upfront duplicate-name check. |
| `git_user_slug` Unicode handling | Still deferred. No non-ASCII contributor surfaced yet. |
| `RepoSpec.worktree` single-component validator | Still deferred. Plan 3's `code add` / `validate` will tighten. |
| `Output.print_rich` leaky abstraction | Plan 2.5 leaves Rich-aware; commands import Rich types directly and use `out.print_rich(...)` for the actual print. Decision: stay Rich-aware, don't add per-type wrappers. |

## New forward debt from Plan 2 (resolved or deferred in Plan 2.5)

| Issue | Resolution |
|---|---|
| `deliverable rm --keep-code` data loss | Fixed (above). |
| `deliverable rename` worktree breakage | Fixed (above). |
| `decision new --supersedes` silent success | Fixed (above). |
| Sibling-consistency bug (B's CLAUDE.md doesn't list A) | Fixed in Plan 2.5 T1.1. |
| Empty `## Sibling deliverables` heading | Fixed in Plan 2.5 T1.2. |
| Global `--quiet`/`--verbose` flags didn't reach `Output` | Fixed in Plan 2.5 T3.1 (Typer Context). |
| Help text missing on ~80% of options | Fixed in Plan 2.5 T3.2. |
| 5 cross-command duplications | Fixed in Plan 2.5 M2 (3 helpers added: `slugify`, `resolve_cli_scope`, `decisions_dir`, `read_phase`, `remove_bullet_under_heading`). |
| Stale `dist/project_cli-*.whl` artifacts | Removed in Plan 2.5 (cleanup commit). |

## Consequences

- All Plan 1 forward-debt items either resolved or marked clearly deferred.
- Plan 3 inherits cleaner foundations — 5 utility helpers already in place
  for the 5+ new commands.
- Plan 1 fixes decision file remains as historical record but its forward-debt
  table is no longer load-bearing; this Plan 2 fixes file is the current
  source of truth for what's deferred.
