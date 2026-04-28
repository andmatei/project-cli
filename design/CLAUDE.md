# project-cli

Python rewrite of the projects workspace CLI
## Workflow
- `scope.md` defines boundaries and success criteria -- set early, changes rarely
- `design.md` (or `tech-design.md`) is the living source of truth for the current technical approach
- `decisions/` contains one file per decision -- question, options explored, conclusion
- When I say "record decision", create a new file in decisions/ with today's date
- When I say "update design", modify design.md to reflect current state
- When I say "update scope", modify scope.md (should be rare)

## Guided Authoring
- `/write-scope` -- guided scope document authoring with brainstorming and review
- `/write-tech-design` -- guided tech design authoring with brainstorming and review
- `/review-scope` -- review scope against MongoDB engineering standards
- `/review-tech-design` -- review tech design against MongoDB engineering standards

## Rules
- Read scope.md and design.md before starting significant work
- After completing a POC or implementation spike, prompt me to update the design
- When a decision is made, create a new file in decisions/
- If implementation reveals the scope needs to change, flag it explicitly
