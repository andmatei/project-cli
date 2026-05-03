# keel

[![CI](https://github.com/andmatei/keel/actions/workflows/ci.yml/badge.svg)](https://github.com/andmatei/keel/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

A scope-driven development scaffolder — the keel is the first structural element
laid down on a ship, and everything else is built relative to it; scope is laid
first here too, separate and load-bearing, with design and decisions built on top.

Concretely: a CLI for managing a personal "projects workspace" — a directory of
design documents, decision records, and code worktrees, one folder per project.
Each project (and optionally each deliverable inside a project) gets its own
scope, design, decisions, and `.phase` lifecycle marker. A per-unit TOML manifest
records linked source repositories so a fresh clone of the workspace can
reconstruct local worktrees.

This is a personal-tool flavor — it scratches a specific itch (a flat list of
`~/projects/<name>/` workspaces) — but it is published in case the structure
or the modules are useful to others.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/andmatei/keel.git
cd keel
uv tool install --editable .

keel --help
```

Optionally install shell completion:

```bash
keel completion zsh --install   # or bash, fish
```

## Quick start

```bash
# Create a new project
keel new my-project -d "Build a thing"

# Add a deliverable (mini-project nested under the parent)
keel deliverable add my-project api -d "REST API surface"

# Record a decision without opening an editor
keel decision new "Pick the storage backend" --no-edit

# Advance the phase
keel phase designing

# Export design + decisions to a single markdown document
keel design export
```

## Commands

### Project lifecycle

| Command | Purpose | Example |
|---|---|---|
| `new` | Create a new project workspace | `keel new my-project -d "..."` |
| `list` | List projects, optionally filtered | `keel list --phase implementing` |
| `list --active` | Show only projects with active milestones/tasks | `keel list --active` |
| `show` | Show a project's structure and state | `keel show my-project` |
| `show --brief` | Skip milestone/task summary (faster) | `keel show my-project --brief` |
| `phase` | Show or transition the lifecycle phase | `keel phase implementing` |
| `validate` | Check project structure and content | `keel validate --content` |
| `archive` | Soft-delete: remove worktrees, move to `.archive/` | `keel archive my-project` |
| `restore` | Restore a project from `.archive/` | `keel restore my-project` |
| `rename` | Rename directory, worktrees, and branch prefixes | `keel rename old-name new-name` |

`show` and most commands auto-detect the project from `$PWD`:

```bash
cd ~/projects/my-project/design && keel show
```

See `keel <cmd> --help` for the full flag surface (dry-run, --json, --yes, etc.).

### Deliverables

Mini-projects nested under a parent project; each gets its own `design/`, decisions, and code linkage.

| Command | Purpose | Example |
|---|---|---|
| `deliverable add` | Create a new deliverable | `keel deliverable add my-project api -d "..."` |
| `deliverable list` | List deliverables in a project | `keel deliverable list my-project` |
| `deliverable rename` | Rename a deliverable | `keel deliverable rename my-project api rest-api` |
| `deliverable rm` | Remove a deliverable and its artefacts | `keel deliverable rm my-project api` |

### Decisions

One file per decision, stored under `design/decisions/` at the project or deliverable scope.

| Command | Purpose | Example |
|---|---|---|
| `decision new` | Create a decision record | `keel decision new "Use Postgres" --no-edit` |
| `decision list` | List decisions at the current scope | `keel decision list` |
| `decision show` | Print a decision file | `keel decision show 2024-01-15-use-postgres` |
| `decision rm` | Delete a decision file | `keel decision rm 2024-01-15-use-postgres` |

To supersede an existing decision: `keel decision new "Switch to SQLite" --supersedes 2024-01-15-use-postgres`.

### Code linkage

Manifest-driven worktrees: source repos are declared in `project.toml` and can be materialized on any machine.

| Command | Purpose | Example |
|---|---|---|
| `code list` | List repos declared in the manifest | `keel code list` |
| `code status` | Show per-repo worktree status | `keel code status` |
| `code init` | Materialize worktrees from the manifest | `keel code init --clone-missing` |
| `code add` | Add a repo to the manifest and create its worktree | `keel code add ~/some-repo` |
| `code rm` | Remove a repo from the manifest and its worktree | `keel code rm some-repo` |

### Design export

```bash
keel design export                        # design.md + decisions, stdout
keel design export --include-scope        # prepend scope.md
keel design export --no-deliverables      # parent project only
keel design export -o exported.md         # write to file
```

### Migration and polish

| Command | Purpose | Example |
|---|---|---|
| `migrate` | Migrate legacy Bash-CLI projects to manifest format | `keel migrate my-project --apply` |
| `completion` | Print or install shell completion | `keel completion zsh --install` |

### Project name resolution

Most commands accept the project name in one of three ways:

1. **Positional argument**: `keel show foo`, `keel validate foo`, `keel archive foo`, `keel rename foo bar`, `keel migrate foo`, `keel design export foo`.
2. **`--project NAME` flag**: works on every command.
3. **CWD auto-detection**: when run from inside `~/projects/<name>/...`, the project is inferred. Pass `--project` to override.

A few commands (`phase`, `deliverable *`, `decision *`, `code *`) do not have a positional project argument because their positional slot is taken by something else (a target phase, a deliverable name, etc.). Use `--project NAME` or CWD detection on those.

## How the workspace is laid out

The CLI manages directories under `$PROJECTS_DIR` (default: `~/projects`).

```
~/projects/
└── <project-name>/
    ├── design/
    │   ├── CLAUDE.md           # human-narrative + manifest summary (generated)
    │   ├── project.toml        # manifest: source of truth for code linkage
    │   ├── scope.md
    │   ├── design.md
    │   ├── .phase              # current phase + history
    │   └── decisions/
    │       └── YYYY-MM-DD-slug.md
    ├── code/                   # git worktree (or code-<repo>/ if multiple)
    └── deliverables/           # mini-projects nested under the parent
        └── <name>/
            ├── design/
            │   └── ...
            └── code/
```

`project.toml` is the manifest source of truth for code linkage and deliverable
references. `CLAUDE.md` is generated from it and kept in sync by `keel`.

## Migrating an existing Bash-CLI workspace

If you used the older `~/projects/bin/project` Bash CLI, `keel migrate` converts
legacy projects to manifest format:

```bash
# Preview what would change (dry-run by default)
keel migrate my-project

# Migrate one project
keel migrate my-project --apply

# Migrate every legacy project at once
keel migrate --all --apply
```

## Milestones, tasks, and ticketing

keel supports dependency-tracked milestones and tasks via DAG topology and ready-task queries:

```bash
keel milestone add m1 --title "Foundation"
keel task add t1 --milestone m1 --title "Set up"
keel task add t2 --milestone m1 --title "Deps" --depends-on t1
keel task next                          # print the topologically-first ready task
keel task next --start                  # start it immediately (planned → active, records branch)
keel task start t1                      # records branch, planned → active
keel task done t1                       # active → done
keel task list --ready                  # shows t2 (now unblocked)
keel task graph                         # ASCII tree of the DAG
keel show my-project                    # shows active tasks + ready-next hints (if milestones.toml exists)
```

For ticketing integration, keel ships a `TicketProvider` Protocol and
entry-point discovery mechanism. Real providers ship as separate PyPI packages.
The first one is `keel-jira` (Atlassian Jira Cloud) and lives in this repo at
[`plugins/jira/`](plugins/jira/). Install it with:

```bash
pip install "keel-cli[jira]"   # equivalent to: pip install keel-cli keel-jira
```

…then configure `project.toml`:

```toml
[extensions.ticketing]
provider = "jira"
parent_id = "PROJ-123"

[extensions.ticketing.jira]
url = "https://your-workspace.atlassian.net"
project_key = "PROJ"
```

…and provide credentials via env vars (`KEEL_JIRA_EMAIL`, `KEEL_JIRA_TOKEN`).
See [`plugins/jira/README.md`](plugins/jira/README.md) for the full setup.

`keel plugin list` shows the registered provider when installed; `keel plugin
doctor` validates your config end-to-end.

### Where plugins live

First-party plugins keel maintains live under `plugins/<name>/` in this
monorepo, each as its own Python package with its own `pyproject.toml` and
its own PyPI release. The repo is set up as a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/),
so cross-plugin development works without `pip install -e` shenanigans.

**External plugin authors** don't need to live here. Write `your-name/keel-foo`
in your own GitHub repo, register a `keel.ticket_providers` (or
`keel.commands`, `keel.phase_preflights`, `keel.phase_transitions`)
entry point in your `pyproject.toml`, publish to PyPI, and `pip install
keel-foo` will plug it in via discovery — no fork or PR to this repo
required. See [`plugins/jira/`](plugins/jira/) as a working reference
implementation. The plugin contract is documented in
[`CONTRIBUTING.md`](CONTRIBUTING.md#authoring-a-plugin) and the rationale
for this dual layout (first-party in monorepo, third-party anywhere) is in
[`design/decisions/2026-05-04-monorepo-for-first-party-plugins.md`](design/decisions/2026-05-04-monorepo-for-first-party-plugins.md).

## Customizable phase lifecycles

By default, projects use a 6-phase lifecycle:
`scoping → designing → poc → implementing → shipping → done`. You can define
custom lifecycles as TOML files under `~/projects/.keel/lifecycles/<name>.toml`
and pick one at project creation:

```bash
keel lifecycle init research        # scaffold a starter TOML
$EDITOR ~/projects/.keel/lifecycles/research.toml
keel lifecycle validate ~/projects/.keel/lifecycles/research.toml
keel new my-paper -d "Q3 paper" --lifecycle research
keel phase --list-next               # follows the FSM you defined
```

Inspect what's available:

```bash
keel lifecycle list
keel lifecycle show default
```

A lifecycle is modelled as a finite-state machine: a set of named states,
allowed transitions between them, an initial state for new projects, and
terminal states. If a `cancelled` state is declared, every state with
`cancellable = true` (the default) gets an implicit `<state> → cancelled`
edge; lifecycles without a `cancelled` state simply don't support
cancellation.

## Roadmap

Plans 1–7 have all shipped, plus the first plugin (`keel-jira`):

- **Plan 1 — Foundation:** core modules + `new`, `list`, `show`
- **Plan 2 — Deliverable, decision, phase:** `deliverable`, `decision`, `phase`
- **Plan 2.5 — Cleanup:** small fixes and refactors
- **Plan 3 — Validate, export, code, archive, rename:** `validate`, `design export`, `code`, `archive`, `rename`
- **Plan 4 — Migration, completion, cutover:** `migrate`, `completion`, workspace cutover + rename to `keel`
- **Plan 4.5 — Pre-plan-5 cleanup:** API surface stabilization, testing fixtures, error-code enum
- **Plan 5 — Milestones, tasks, ticketing:** `milestone`, `task`, plugin protocol
- **Plan 5.1 — Simplification:** helpers, `jira_id` → `ticket_id`, dead code removal
- **Plan 5.2 — API consistency:** `--dry-run`, JSON shapes, help text
- **Plan 5.3 — Documentation truth:** README/scope/plans cleanup, public-repo readiness
- **Plan 5.4 — API completion + code health:** `manifest/` package split, `get_milestone`/`get_task`, public-API discipline
- **Plan 5.5 — Visibility wins:** `keel show` milestone summary, `task next`, `list --active`, `restore`
- **Plan 6 — Extensibility hardening:** phase preflights, `phase --list-next`, `keel plugin` group
- **Plan 7 — Customizable phase lifecycles:** FSM-based lifecycles, `keel lifecycle` group
- **Plugin: keel-jira (`plugins/jira/`)** — first real `TicketProvider`

See [`design/plans/`](design/plans/) for the implementation plan documents and
[`design/decisions/`](design/decisions/) for the rationale behind major choices.

## Development

```bash
git clone https://github.com/andmatei/keel.git
cd keel

# Run tests
uv run --extra dev pytest

# Run from source without installing globally
uv run python -m keel --help
```

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for development
setup, conventions, and the review process.

## Security

To report a security issue, see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE).
