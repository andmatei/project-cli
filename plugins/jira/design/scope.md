# keel-jira — scope

`keel-jira` is the first real `TicketProvider` plugin for [keel](https://github.com/andmatei/keel).
It implements the `keel.ticketing.base.TicketProvider` Protocol against the
Atlassian Jira Cloud REST API v3.

## In scope

- Implementing `TicketProvider` against Jira Cloud (`*.atlassian.net`) REST API v3.
- Authentication via API token + email (`KEEL_JIRA_TOKEN` env var, `KEEL_JIRA_EMAIL` env var).
- The 6 protocol methods: `configure`, `create_milestone`, `create_task`,
  `transition`, `fetch`, `link_url`.
- Mapping keel's neutral states (`planned`/`active`/`done`/`cancelled`) to a
  configurable Jira workflow status set.
- Configuration via `[extensions.ticketing.jira]` block in a project's
  `project.toml`.
- A small HTTP client wrapper around `httpx` — no `jira` or
  `atlassian-python-api` dependency.
- Tests: pytest + `respx` for unit mocks; one optional manual integration smoke
  gated by env vars.

## Out of scope (v0.1)

- Jira Server / Data Center support. Cloud only.
- OAuth or PAT auth. API token only.
- Custom fields beyond the basics required by the protocol (epic links, sprints).
- Bulk operations.
- Two-way sync (live polling, status drift detection).
- A standalone `keel-jira` CLI. The plugin is consumed via `keel`'s commands.

## Success criteria

- `pip install keel-cli keel-jira` makes `keel milestone add --push` create a
  Jira issue and store its key in `milestones.toml`.
- `keel milestone done` transitions the matching Jira issue to a "Done"-mapped
  status.
- `keel plugin list` shows the jira provider when installed.
- `keel plugin doctor` validates the project's `[extensions.ticketing.jira]`
  config and confirms credentials work.
- The package is independently installable, versioned, and published to PyPI as
  `keel-jira`.
- Unit tests pass without network access (via `respx`); manual smoke tests
  exercise a real Jira instance.
