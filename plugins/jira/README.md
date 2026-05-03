# keel-jira

Jira Cloud `TicketProvider` plugin for [keel](https://github.com/andmatei/keel).

Lets keel push milestones and tasks into Jira issues, transition them as the
work moves through your phase lifecycle, and link back to the Jira UI.

## Install

```bash
pip install keel-cli keel-jira
# or, equivalently, via keel-cli's extra:
pip install "keel-cli[jira]"
```

## Configure

In your project's `project.toml`:

```toml
[extensions.ticketing]
provider = "jira"
parent_id = "PROJ-123"   # the Epic that milestones become Stories under

[extensions.ticketing.jira]
url = "https://your-workspace.atlassian.net"
project_key = "PROJ"
status_map = { planned = "To Do", active = "In Progress", done = "Done", cancelled = "Cancelled" }
```

Credentials live in your environment (never in the manifest):

```bash
export KEEL_JIRA_EMAIL="you@example.com"
export KEEL_JIRA_TOKEN="atlassian-api-token-here"
```

Get an API token from <https://id.atlassian.com/manage-profile/security/api-tokens>.

## Use

Once installed and configured, `keel`'s existing commands push to Jira automatically:

```bash
keel milestone add m1 --title "Foundation"   # creates a Story under PROJ-123
keel milestone done m1                       # transitions to "Done"
keel task add t1 --milestone m1 --title "x"  # creates a Subtask
```

`--no-push` on any of these skips the Jira call.

`keel plugin list` shows the registered provider; `keel plugin doctor` checks
your config and credentials.

## Status

v0.1 — Cloud only, API token auth, basic create / transition / fetch.
Server / Data Center, OAuth, custom fields, bulk operations, and two-way sync
are out of scope for v0.1.

## License

MIT.
