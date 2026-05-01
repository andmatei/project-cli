# Contributing to keel

Thanks for your interest in contributing! This document describes how to set
up a development environment, the conventions used in the codebase, and how
contributions are reviewed.

## Development setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/andmatei/keel.git
cd keel

# Run tests in an isolated venv (uv handles deps automatically)
uv run --extra dev pytest

# Install the CLI for end-to-end testing
uv tool install --editable .
keel --help

# Install pre-commit hooks (runs ruff check + format on every commit)
uv tool install pre-commit
pre-commit install
```

Tests are isolated via a `PROJECTS_DIR` environment override and `pytest`'s
`tmp_path` fixture; they don't touch your real `~/projects/`. Git operations
in tests use real `git init`'d repos in `tmp_path` (no mocks).

## Linting and formatting

`ruff check` and `ruff format` both run in CI. Local pre-commit hooks
(installed via the step above) run them on every commit, so you generally
won't need to run them by hand. To run on demand:

```bash
uv run --extra dev ruff check src tests
uv run --extra dev ruff format src tests   # rewrites; use --check to dry-run
pre-commit run --all-files                 # runs everything the hooks would
```

## Conventions

### Code style

- Python 3.11+ (`from __future__ import annotations`, modern union syntax).
- One module, one responsibility. Files stay small (typically <150 lines).
- No emoji in code or docs unless explicitly requested.
- Comments are reserved for non-obvious *why* — not *what* (the code says
  that).

### Commit messages

The project uses Conventional Commits-flavored prefixes:

- `feat(area): ...` — new functionality
- `fix(area): ...` — bug fix
- `test(area): ...` — adding or improving tests
- `docs(area): ...` — documentation only
- `refactor(area): ...` — no behavior change
- `chore(area): ...` — tooling/build/repo housekeeping

Where `area` is typically the affected module or command (`new`, `manifest`,
`workspace`, etc.). Commit subject lines stay under ~70 characters; the body
explains the *why*.

### Testing

- TDD discipline: write the failing test before the implementation.
- Each command has both behavioral tests (does the right thing happen on
  disk?) and contract tests (`--json` payload shape, exit code).
- New commands or modules need their own dedicated test file.

### Pull requests

- One PR per logical change.
- Description should explain the *why* and link any relevant decision
  document under `design/decisions/` if the change reflects a design
  decision.
- All CI checks (tests, lint when present) must pass before review.
- Reviews focus on: spec compliance (does it do what the linked plan/issue
  asks?), then code quality (clean, well-tested, well-named).

## Where things live

```
src/keel/
├── app.py                  # Typer top-level app + global flags
├── manifest.py             # Pydantic models + TOML I/O
├── workspace.py            # paths + CWD scope detection
├── markdown_edit.py        # AST-aware markdown section editing
├── templates.py            # Jinja2 renderer (templates in _templates/)
├── output.py               # human + JSON output module
├── dryrun.py               # OpLog for --dry-run
├── prompts.py              # TTY-aware prompts (questionary)
├── git_ops.py              # subprocess wrapper for git
└── commands/               # one module per subcommand

tests/
├── conftest.py             # shared fixtures (projects, source_repo, …)
├── test_*.py               # one per source module
└── commands/test_*.py      # one per command module

design/
├── scope.md
├── design.md
├── decisions/              # one .md per non-obvious choice
└── plans/                  # implementation plans (Plan 1, Plan 2, ...)
```

## Design documents

Major changes are captured as a *decision file* under `design/decisions/`. The
filename follows `YYYY-MM-DD-<slug>.md` and the body has frontmatter (`date`,
`title`, `status`) plus sections for question, options explored, conclusion,
and consequences. Pull requests that change architecture should add or update
a decision file alongside the code.

## Reporting bugs

Use the [bug report issue template](.github/ISSUE_TEMPLATE/bug.md). Include:

- Reproduction steps
- Expected vs actual behavior
- `keel --version`, OS, Python version
- Relevant `--verbose` output if applicable

## Reporting security issues

See [SECURITY.md](SECURITY.md). Please do not file public issues for
suspected vulnerabilities.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](LICENSE).
