---
date: 2026-04-29
title: Pure-plugin ticketing model — no bundled providers in keel core
status: accepted
---

# Pure-plugin ticketing model — no bundled providers in keel core

## Question

When designing the ticketing integration, should keel core bundle one provider
(e.g. Jira) for "out-of-box" ergonomics, or should ALL providers be plugins —
including the ones the maintainer uses?

## Options explored

### Option A: Bundle Jira in core; treat others as plugins

- Pros: zero-friction Jira usage (just `pip install keel-cli`).
- Cons: keel core gains a Jira-specific dependency tree; users who don't use
  Jira pay (download size, bug surface). Two ticketing code paths from day
  one (the bundled one and the plugin one). Plugin protocol risks getting
  shaped around Jira's quirks rather than designed for arbitrary providers.

### Option B: Bundle Jira as a plugin shipped in the same wheel

- Pros: the protocol is the only protocol; bundled provider validates the
  plugin pattern end-to-end.
- Cons: still ships Jira-specific code to non-Jira users.

### Option C: Pure separation — keel core ships only the protocol + a mock

- Pros: keel core stays minimal and dependency-free for ticketing. Real
  providers (`keel-jira`, `keel-github`, `keel-linear`, `keel-notion`) are
  separate packages, each developed and maintained on its own cadence.
  Plugin protocol is never tempted to specialise for one provider. Users
  install only what they use.
- Cons: a Jira user must explicitly `pip install keel-jira`.

## Conclusion

**Option C.** keel-cli ships only the `TicketProvider` protocol, the
plugin-discovery mechanism (Python entry points), and a `MockProvider` for
tests. No real provider — including Jira — lives in core. `keel-jira` is a
separate, developed-and-maintained package; same for any future provider.

## Consequences

- The plugin protocol must be designed for arbitrary providers from the
  start; no Jira-specific shortcuts.
- Plan 5 (this plan) implements core. Plan 6 implements the first real
  plugin (`keel-jira`), as its own package.
- Users who want ticketing run `pip install keel-cli keel-jira` (or similar).
  This becomes the documented install command for that workflow.
- Test coverage for the protocol uses the `MockProvider`; integration with
  real services is the responsibility of each plugin package's own test
  suite.
