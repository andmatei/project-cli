# Security Policy

## Supported versions

`project-cli` is in active development. Only the latest release on `main`
receives security fixes.

## Reporting a vulnerability

**Please do not file public issues for security vulnerabilities.**

Instead, use GitHub's private vulnerability reporting at
<https://github.com/andmatei/project-cli/security/advisories/new>.

When reporting, please include:

- A description of the vulnerability
- Steps to reproduce (proof-of-concept welcome)
- The version of `project-cli` you're running
- Any suggested mitigation

You can expect an acknowledgement within a few business days.

## Scope notes

`project-cli` is a personal-workspace CLI that touches:

- The local filesystem under `$PROJECTS_DIR` (default: `~/projects`)
- The git CLI (subprocess) for worktree management
- The user's `$EDITOR` (in future commands)

It does not handle authentication, network secrets, or remote services. The
most plausible vulnerability classes are:

- Path-traversal via untrusted project names or worktree paths
- Argument injection into the `git` subprocess
- TOML or markdown parsing that mis-handles adversarial input

If you find any of the above (or something else), please report it.
