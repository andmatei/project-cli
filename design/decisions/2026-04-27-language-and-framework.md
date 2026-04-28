---
date: 2026-04-27
title: Language and framework for the projects CLI rewrite
status: accepted
---

# Language and framework for the projects CLI rewrite

## Question

The existing CLI at `~/projects/bin/project` is ~1000 lines of Bash split across
a dispatcher + 7 subcommand files + 3 lib files + 6 markdown templates. Pain
points: BSD-only `sed -i ''` for cross-file mutation, `envsubst` templating via
exported `TPL_*` vars, ad-hoc `.phase` file format, no tests, repeated argument
parsing per subcommand. What language and framework should the rewrite use?

## Options explored

### Option A: Python + Typer (chosen)

- **Pros**: lowest install friction (`uv tool install --editable .`); best CLI
  DX (Typer's annotations); strongest ecosystem for *this tool's actual work* —
  `markdown-it-py` for AST-aware markdown editing, `Jinja2` for templates,
  `Pydantic` for typed manifest schema, `tomlkit` for round-trip TOML I/O,
  `questionary` for prompts, `Rich` for output, `pytest` for tests; fast
  iteration (no compile cycle); Python ≥3.11 already on host.
- **Cons**: ~80ms cold-start (vs <10ms for compiled binary); runtime dependency
  (mitigated by `uv tool install`).

### Option B: Python + Click

- Same upsides as Typer; slightly more verbose; more battle-tested. Picked
  Typer for the cleaner annotation-based subcommand definition.

### Option C: Go + Cobra

- **Pros**: single static binary; <10ms startup; strong types.
- **Cons**: more boilerplate; markdown AST ecosystem (goldmark) lags
  `markdown-it-py` for the kind of structural mutations we need (insert under
  named heading, idempotent re-edits); slower iteration; for a personal tool
  the binary-distribution wins don't apply.

### Option D: Rust + clap

- **Pros**: fastest, smallest binary; strongest type safety; `clap` derive API
  is excellent.
- **Cons**: highest iteration cost (borrow checker tax + compile times);
  markdown AST manipulation more verbose; for a personal tool we'll keep
  editing, the iteration cost isn't worth the runtime gains we don't need.
  Genuinely over-engineered here.

### Option E: Bun + TypeScript

- **Pros**: `unified/remark` is the best markdown-AST ecosystem on any
  platform; native TypeScript; `bun build --compile` produces a single binary.
  Defensible alternative.
- **Cons**: smaller community than Node; ~5% chance of hitting a Node-compat
  edge case; no widely-adopted CLI built on Bun yet (no `ripgrep`/`gh`-class
  example to crib from); user does not have an existing TS habit visible in
  this workspace, so learning + edge-case-debugging tax outweighs wins for
  this specific tool.

## Conclusion

**Chose A — Python + Typer.** The work this CLI does (markdown templating,
AST-aware mutation of cross-file references, manifest schema validation,
shelling out to git, interactive prompts) maps onto Python's ecosystem
unusually well. Iteration speed dominates total cost for a personal tool the
user will keep editing. Distribution friction is zero —
`uv tool install --editable .` gives a clean local install with fast edit
loops.

Bun + TS is the second-best choice if a single binary or stronger types ever
become necessary; revisit if those constraints emerge.

## Consequences

- Stack locked: Typer + Rich + Pydantic v2 + markdown-it-py + Jinja2 + tomlkit
  + questionary + pytest.
- Install via `uv tool install --editable .` (or `pipx install -e .`).
- `pyproject.toml` is the canonical project file; version read from it via
  `importlib.metadata`.
- Slash commands (`/decide`, `/phase`, `/export-design`, etc.) keep their
  current names but their bodies are rewritten to invoke the new CLI.
- Existing Bash CLI stays in place during the rewrite; cutover strategy is an
  open question to be settled in the implementation plan.
