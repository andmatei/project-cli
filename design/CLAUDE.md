# keel — design conventions

This `design/` directory contains the project's living documentation:

- **`scope.md`** — boundaries and success criteria. Set early, changes rarely.
- **`design.md`** — living technical design. Update as understanding evolves.
- **`decisions/`** — one file per decision (`YYYY-MM-DD-slug.md`). Record question, options explored, conclusion. Use `keel decision new <title>` to scaffold.
- **`plans/`** — implementation plans, one per logical milestone. Historical record once shipped.

## Working with these docs

- Read `scope.md` and `design.md` before starting significant work.
- After completing a substantive implementation, update `design.md` to reflect current state.
- When a decision is made, run `keel decision new <title>`.
- If implementation reveals scope needs to change, flag it explicitly in a decision file rather than silently amending `scope.md`.
