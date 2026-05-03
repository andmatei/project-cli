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
├── api.py                  # public stable surface; what plugins import from
├── manifest.py             # Pydantic models + TOML I/O
├── workspace.py            # paths + CWD scope detection
├── markdown_edit.py        # AST-aware markdown section editing
├── templates.py            # Jinja2 renderer (templates in _templates/)
├── output.py               # human + JSON output module
├── dryrun.py               # OpLog for --dry-run
├── prompts.py              # TTY-aware prompts (questionary)
├── git_ops.py              # subprocess wrapper for git
├── lifecycle.py            # PHASES, MILESTONE_STATES, TASK_STATES, transition validators
├── errors.py               # ErrorCode StrEnum and HINT_* constants
├── milestones.py           # pure-graph DAG helpers (validate_dag, ready_tasks, blocked_tasks, topological_sort)
├── util.py                 # slugify and other tiny helpers
├── ticketing/              # TicketProvider Protocol + MockProvider + entry-point registry
├── testing/                # pytest fixtures (projects, make_project, make_deliverable, source_repo, mock_ticket_provider)
├── _templates/             # Jinja2 templates (internal; overriding requires forking)
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

## Adding a new command

For a top-level command (e.g. `keel foo`):

1. Create `src/keel/commands/foo.py` exposing `cmd_foo(ctx: typer.Context, ...)`.
2. Register in `src/keel/app.py` after the existing `from keel.commands.X import cmd_X` block:
   ```python
   from keel.commands.foo import cmd_foo  # noqa: E402
   app.command(name="foo")(cmd_foo)
   ```
3. Add tests in `tests/commands/test_foo.py` using the `projects` and `make_project` fixtures from `keel.testing`.

For a command group (e.g. `keel bar add` / `keel bar list`):

1. Create `src/keel/commands/bar/__init__.py` with a Typer subapp and per-command imports (mirror `commands/decision/__init__.py`).
2. Create one file per subcommand (`add.py`, `list.py`, etc.).
3. Register the subapp in `app.py` via `app.add_typer(bar_app, name="bar")`.

For a third-party plugin: register via the `keel.commands` entry-point group in your plugin's `pyproject.toml`. See the docstring at `src/keel/app.py` for the contract.

## Authoring a plugin

keel exposes four entry-point groups that plugins can hook into. Plugin packages
declare these in their `pyproject.toml` under `[project.entry-points]`.

**Where plugins live.** First-party plugins keel maintains live under
[`plugins/<name>/`](plugins/) in this monorepo as a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/);
each is a separate Python package with its own `pyproject.toml` and PyPI
release. See [`plugins/jira/`](plugins/jira/) for a worked example.

**Third-party plugins** can live wherever the author wants — your own GitHub
repo, your own PyPI namespace, no fork or PR required. As long as you publish
a wheel that registers the right entry point, `pip install your-plugin` will
make keel discover it. The first-party / third-party split exists for
maintainer convenience, not as a permission boundary; the public plugin
contract is the same. The rationale (and migration triggers if the monorepo
ever becomes the wrong shape) is in
[`design/decisions/2026-05-04-monorepo-for-first-party-plugins.md`](design/decisions/2026-05-04-monorepo-for-first-party-plugins.md).

### `keel.commands` — register a CLI command

```toml
[project.entry-points."keel.commands"]
my_cmd = "my_pkg.cli:register"
```

```python
# my_pkg/cli.py
import typer

def register(app: typer.Typer) -> None:
    app.command(name="my-cmd")(my_func)
```

### `keel.ticket_providers` — implement the `TicketProvider` Protocol

See `keel.ticketing.base.TicketProvider` and the reference `MockProvider`.

```toml
[project.entry-points."keel.ticket_providers"]
jira = "keel_jira.provider:JiraProvider"
```

### `keel.phase_preflights` — add preflight checks for phase transitions

```toml
[project.entry-points."keel.phase_preflights"]
my_rules = "my_pkg.preflights:get_preflights"
```

```python
# my_pkg/preflights.py
from keel.api import PhasePreflight, PreflightResult

class TicketsAcceptedPreflight:
    name = "tickets-accepted"
    def check(self, scope, from_phase, to_phase):
        if to_phase != "implementing":
            return PreflightResult()
        # ... query ticketing system ...
        return PreflightResult(warnings=[]) if accepted else PreflightResult(blockers=["..."])

def get_preflights():
    return [TicketsAcceptedPreflight()]
```

### `keel.phase_transitions` — react after a successful transition

```toml
[project.entry-points."keel.phase_transitions"]
my_hook = "my_pkg.hooks:on_transition"
```

```python
# my_pkg/hooks.py
def on_transition(scope, from_phase, to_phase):
    # Side-effect only. Errors are caught and logged via out.warn.
    print(f"transitioned {from_phase} -> {to_phase}")
```

## Authoring a custom lifecycle

Custom workflows live as TOML files under
`~/projects/.keel/lifecycles/<name>.toml`. They override built-ins of the
same name. Schema fields:

- `name` (string, required): must match the filename stem.
- `description` (string, optional).
- `initial` (string, required): starting state for new projects.
- `terminal` (list[string], required): one or more states marking completion.
- `[states.<name>]` (one per state): supports `description` and
  `cancellable` (default `true`).
- `[transitions]` (table): `<from> = ["<to1>", "<to2>", ...]`.

An example minimal lifecycle:

```toml
name = "research"
description = "Research project lifecycle."
initial = "proposing"
terminal = ["published", "cancelled"]

[states.proposing]
[states.reviewing]
[states.executing]
[states.published]
[states.cancelled]

[transitions]
proposing = ["reviewing"]
reviewing = ["executing", "proposing"]
executing = ["published"]
```

Run `keel lifecycle validate <path>` to lint a TOML; `keel lifecycle init
<name>` scaffolds a placeholder.

### Testing your plugin

`pip install --extra dev keel-cli`, then in your `tests/conftest.py`:

```python
pytest_plugins = ["keel.testing"]
```

You get the `projects`, `make_project`, `make_deliverable`, `source_repo`, and
`mock_ticket_provider` fixtures for free. `MockProvider` is also re-exported
from `keel.testing` for use in non-fixture contexts.

### Inspecting installed plugins

`keel plugin list` shows everything registered across the four groups.
`keel plugin doctor` validates that the current project's `[extensions]` config
points at installed plugins and that providers can be instantiated.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](LICENSE).
