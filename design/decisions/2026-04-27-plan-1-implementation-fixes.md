---
date: 2026-04-27
title: Plan 1 implementation fixes and forward debt
status: superseded
---

# Plan 1 implementation fixes and forward debt

> **Superseded by `2026-04-28-plan-2-implementation-fixes.md`** for the
> forward-debt list. The implementation-fixes section below is still
> historically accurate; the forward-debt section is now stale (most items
> resolved by Plan 2 or Plan 2.5).

Captures non-obvious implementation choices made during Plan 1 execution and
items the final code review flagged as forward debt for Plans 2-4. Recorded
here so future agents don't have to reverse-engineer them from commit messages.

## Implementation-time fixes (already committed)

- **TOML date format** (commit `fcf64ac`). Plan code used `model_dump(mode="json")`
  for manifest meta blocks, which serializes `date` as a quoted string. Dropped
  `mode="json"` so tomlkit emits native TOML date literals (`created = 2026-04-27`,
  unquoted). Test asserts the on-disk format.
- **`None`-filter symmetry** (commit `fcf64ac`). Manifest save now applies
  `_dict_no_none` to both meta and repo dicts, not just repos.
- **Rich markup vs `[dry-run]` literal** (commit `309d5ad`). `Output.info()`
  now passes `markup=False` to the stderr console so literal `[bracketed]`
  prefixes survive.
- **Rich vs JSON wrapping** (commit `309d5ad`). `Output.result()` JSON branch
  bypasses Rich entirely (stdlib `print(json.dumps(...))`) to avoid Rich's
  default 80-column line wrapping breaking `json.loads`.
- **`remove_worktree` cwd bug** (commit `3bea370`). Plan code ran
  `git worktree remove` with `cwd=dest.parent`, which is rarely a git repo.
  Fixed to use `git -C <dest>` so it runs inside the worktree being removed.
- **`prompts.py` exit type** (commit `2926ee9`). Plan code used `SystemExit`;
  switched to `typer.Exit` to match the project's idiom. (Tests adjusted —
  `typer.Exit` is a `RuntimeError` subclass, not a `SystemExit` subclass.)
- **Jinja whitespace** (commit `3fef1ab`). Plan's `trim_blocks=False, lstrip_blocks=False`
  produced triple blank lines around conditional sections. Switched to
  `trim_blocks=True, lstrip_blocks=True` and adjusted `claude_md.j2` accordingly.
  Snapshot test asserts no `\n\n\n` in any rendered combination.
- **Typer 0.25 `CliRunner(mix_stderr=False)`** (commits `e296065`, `a6d1314`).
  Argument removed in Typer 0.25 / Click 8.3 because stream separation became
  the default. Tests use bare `CliRunner()` and still observe `result.stderr`
  correctly.

## Forward debt — items deferred to Plan 2+

These were flagged by the final review of Plan 1 and should be addressed when
the next plan touches the relevant code.

- **`replace_section` blank-line behavior** (`markdown_edit.py:108`) — current
  implementation produces inconsistent spacing between replaced body and next
  heading depending on `new_body` newline shape. Plan 2's `code add/rm` /
  `deliverable add/rm` will exercise this. Fix: normalize to exactly one blank
  line. Add a stability test (apply `replace_section` twice with different
  new-body shapes, assert document stabilizes).
- **Multi-repo `Path.name` collision** (`commands/new.py`) — if two `--repo`
  paths share a basename, worktree dirs collide (`code-foo` × 2). Plan 1 leaves
  the failure to `git_ops.create_worktree`'s "destination already exists"
  error, which is confusing. Fix: detect collision in upfront validation,
  emit `code="duplicate_repo_name"` with a clear hint.
- **`git_user_slug` Unicode handling** (`git_ops.py:65`) — `ch.isalnum()` keeps
  non-ASCII alphanumerics, producing non-ASCII branch prefixes for users with
  non-ASCII `user.name`. Decide: tighten to ASCII-only via `unicodedata.normalize`
  + `ch.isascii() and ch.isalnum()`, or document that the workspace requires
  ASCII names. Affects Plan 2's deliverable branch creation.
- **`detect_scope` does not validate existence** (`workspace.py:46-48`) — returns
  a `Scope` for any path that structurally matches `~/projects/<X>/deliverables/<Y>/`,
  even if `<Y>/design/deliverable.toml` doesn't exist. Plan 2's
  `decision new` and `phase` need either a downstream validation step or a
  stricter `detect_scope`.
- **`Output.print_rich` is a leaky abstraction** (`output.py:46`) — exposes
  Rich-specific renderables in the public interface. Decide: commit to
  Rich-aware (`out.tree(...)`, `out.panel(...)`) or stream-only (`Output`
  handles only `info`/`warn`/`error`/`result`; commands print Rich directly).
- **`RepoSpec.worktree` validator allows `"sub/dir"` and `".."`** —
  rejects absolute paths only. Plan 3's `validate` and `code add` should tighten
  this to a single path component.
- **Test gaps to close** — no test for `Output.warn`, `confirm_destructive`,
  `_slugify` edge cases (empty / Unicode / all-symbol / numeric-only),
  on-disk-rejection of an invalid `DeliverableManifest` (only in-memory tested).
  Add when Plan 2 starts touching destructive ops.

## Consequences

- Plan 2's design should explicitly call out which forward-debt items it
  resolves vs defers further. Use the items above as the checklist.
- A Plan 1 retroactive cleanup (e.g., adding the missing tests, hoisting
  function-local imports in `cmd_new`, dropping the unused `Path` import in
  `show.py`) can land as small follow-up commits before Plan 2 starts. Not
  blocking.
- The `git_user_slug` Unicode question is the only one with a real "decision"
  flavor. The others are implementation hardening. If/when a non-ASCII-named
  user contributes, either decide here or in a follow-up decision file.
