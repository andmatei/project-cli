"""`keel phase [PHASE]`."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from keel import workspace
from keel.lifecycle import PHASES
from keel.lifecycle import next_phase as _next_phase
from keel.output import Output


def _phase_path(project: str, deliverable: str | None) -> Path:
    if deliverable:
        return workspace.deliverable_dir(project, deliverable) / "design" / ".phase"
    return workspace.project_dir(project) / "design" / ".phase"


def _read_phase(path: Path) -> tuple[str, list[str]]:
    """Returns (current_phase, history_lines). History lines are everything after line 1."""
    current = workspace.read_phase(path.parent)
    if not path.is_file():
        return current, []
    lines = path.read_text().splitlines()
    return current, lines[1:]


def cmd_phase(
    ctx: typer.Context,
    phase: str | None = typer.Argument(
        None, help="Target phase to transition to. Mutually exclusive with --next."
    ),
    next_phase: bool = typer.Option(False, "--next", help="Advance one step in the lifecycle."),
    deliverable: str | None = typer.Option(
        None, "-D", "--deliverable", help="Phase scope: deliverable instead of project."
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Project name. Auto-detected from CWD if omitted."
    ),
    message: str | None = typer.Option(
        None, "-m", "--message", help="Optional note recorded in the phase history."
    ),
    no_decision: bool = typer.Option(
        False, "--no-decision", help="Skip auto-creating a phase-transition decision file."
    ),
    yes: bool = typer.Option(
        False, "-y", "--yes", help="Skip interactive prompts (description, etc.)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Show or transition the phase."""
    out = Output.from_context(ctx, json_mode=json_mode)

    from keel.workspace import resolve_cli_scope

    scope = resolve_cli_scope(project, deliverable)
    project = scope.project
    deliverable = scope.deliverable

    path = _phase_path(project, deliverable)
    current, history = _read_phase(path)

    if phase is None and not next_phase:
        # Show mode
        scope_name = f"{project}/{deliverable}" if deliverable else project
        if json_mode:
            out.result(
                {
                    "scope": "deliverable" if deliverable else "project",
                    "name": scope_name,
                    "phase": current,
                    "history": [{"line": h} for h in history if h.strip()],
                }
            )
            return
        out.result(
            None,
            human_text=f"{scope_name}\nphase: {current}\n\n" + "\n".join(history)
            if history
            else f"{scope_name}\nphase: {current}",
        )
        return

    # Transition mode
    # Determine target phase
    target = phase
    if next_phase:
        if current not in PHASES:
            out.error(f"invalid current phase: {current}", code="invalid_phase")
            raise typer.Exit(code=1)
        nxt = _next_phase(current)
        if nxt is None:
            out.error(f"no phase after {current}", code="end_of_lifecycle")
            raise typer.Exit(code=1)
        target = nxt

    if target not in PHASES:
        out.error(
            f"invalid phase: {target}. Valid phases: {', '.join(PHASES)}",
            code="invalid_phase",
        )
        raise typer.Exit(code=2)

    if target == current:
        out.info(f"already in phase: {current}")
        return

    # Backwards transition warning
    if PHASES.index(target) < PHASES.index(current):
        from keel.prompts import confirm_destructive

        confirm_destructive(
            f"Backwards phase transition: {current} → {target}. Continue?",
            yes=yes,
        )

    if dry_run:
        from keel.dryrun import OpLog

        log = OpLog()
        log.modify_file(path, diff=f"{current} → {target}")
        if not no_decision:
            today = date.today().isoformat()
            log.create_file(
                workspace.decisions_dir(project, deliverable) / f"{today}-phase-{target}.md", size=0
            )
        out.info(log.format_summary())
        return

    # Apply transition
    today = date.today().isoformat()
    history_line = f"{today}  {current} → {target}"
    if message:
        history_line += f"  ({message})"
    new_lines = [target] + [history_line] + history
    path.write_text("\n".join(new_lines) + "\n")

    # Auto-create phase decision file
    if not no_decision:
        from keel import templates

        _decisions_dir = workspace.decisions_dir(project, deliverable)
        _decisions_dir.mkdir(parents=True, exist_ok=True)
        decision_path = _decisions_dir / f"{today}-phase-{target}.md"
        if not decision_path.exists():
            decision_path.write_text(
                templates.render(
                    "decision_entry.j2",
                    date=today,
                    title=f"Phase transition: {current} → {target}",
                )
            )

    out.info(f"Phase: {current} → {target}")
    out.result(
        {
            "scope": "deliverable" if deliverable else "project",
            "name": f"{project}/{deliverable}" if deliverable else project,
            "phase": target,
            "transitioned_from": current,
        },
        human_text=f"Phase: {current} → {target}",
    )
