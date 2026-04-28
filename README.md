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

## Usage

The current release (Plan 1: foundation) implements three commands plus version
and help. More commands are planned (see [Roadmap](#roadmap)).

### Create a project

```bash
keel new my-project -d "Build a thing" --no-worktree
```

With a source repo (creates a worktree):

```bash
keel new my-project -d "Build a thing" -r ~/some-source-repo
```

Multiple repos:

```bash
keel new multi -d "Two repos" -r ~/repo-a -r ~/repo-b
```

Dry-run (prints planned operations, writes nothing):

```bash
keel new my-project -d "Preview" --no-worktree --dry-run
```

### List projects

```bash
keel list
keel list --phase implementing
keel list --json
```

### Show a project

```bash
keel show my-project
keel show --json my-project
```

`show` auto-detects the project from `$PWD`:

```bash
cd ~/projects/my-project/design && keel show
```

### Global flags

- `--version` — print version and exit
- `-q/--quiet` — suppress info logs (errors still go to stderr)
- `-v/--verbose` — extra debug output
- `NO_COLOR` env var — honored

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

See [`design/scope.md`](design/scope.md) and [`design/design.md`](design/design.md)
for the full specification, including the planned `deliverable`, `decision`,
`phase`, `validate`, `archive`, `rename`, `code`, and `design export`
subcommands.

## Roadmap

Plan 1 (this release) is one of four planned chunks:

- **Plan 1 — Foundation (shipped):** core modules + `new`, `list`, `show`
- **Plan 2 — Deliverable, decision, phase**
- **Plan 3 — Validate, design export, code group, archive, rename**
- **Plan 4 — Migration, completion, shell-completion install, cutover**

Each plan ships independently usable software. See
[`design/plans/`](design/plans/) for the implementation plan documents.

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
