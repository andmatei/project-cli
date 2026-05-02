"""`keel phase [PHASE]`."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from keel import templates, workspace
from keel.api import (
    ErrorCode,
    LifecycleNotFoundError,
    OpLog,
    Output,
    confirm_destructive,
    load_lifecycle,
    load_project_manifest,
    resolve_cli_scope,
)
from keel.phase_events import fire_phase_transition
from keel.preflights import iter_preflights
from keel.workspace import project_dir


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
    strict: bool = typer.Option(False, "--strict", help="Treat preflight warnings as blockers."),
    force: bool = typer.Option(False, "--force", help="Skip preflight checks entirely."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip the warning confirmation prompt."),
    list_next: bool = typer.Option(
        False,
        "--list-next",
        help="Print the valid next phase(s) from the current state and exit (no transition).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Show or transition the phase."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    project = scope.project
    deliverable = scope.deliverable

    path = scope.phase_file
    current, history = _read_phase(path)

    # Load the project's lifecycle (deliverables inherit from their parent project)
    try:
        project_manifest_path = project_dir(scope.project) / "design" / "project.toml"
        manifest = load_project_manifest(project_manifest_path)
        lc = load_lifecycle(manifest.project.lifecycle)
    except LifecycleNotFoundError as e:
        out.fail(
            f"lifecycle not found: {e}",
            code=ErrorCode.NOT_FOUND,
        )

    # --list-next mode: show valid next transitions and exit
    if list_next:
        nexts = lc.successors(current) if current in lc.states else []
        if json_mode:
            out.result({"current": current, "next": nexts})
        else:
            if nexts:
                out.info(f"Current: {current} → next: {', '.join(nexts)}")
            else:
                out.info(f"Current: {current} (end of lifecycle)")
        return

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
        if current not in lc.states:
            out.fail(f"invalid current phase: {current}", code=ErrorCode.INVALID_PHASE)
        explicit_successors = [s for s in lc.successors(current) if s != "cancelled"]
        if not explicit_successors:
            out.fail(
                f"no forward transition from '{current}' (state is terminal or has no non-cancel edges)",
                code=ErrorCode.END_OF_LIFECYCLE,
            )
        target = explicit_successors[0]

    # Validate target state is known
    if target not in lc.states:
        out.fail(
            f"unknown phase '{target}' for lifecycle '{lc.name}'",
            code=ErrorCode.INVALID_PHASE,
        )

    # Validate transition is allowed (unless it's a no-op)
    if target != current and target not in lc.successors(current):
        out.fail(
            f"cannot transition from '{current}' to '{target}' "
            f"(allowed: {', '.join(lc.successors(current)) or 'none'})",
            code=ErrorCode.INVALID_STATE,
        )

    if target == current:
        out.info(f"already in phase: {current}")
        return

    # Run preflights
    if not force and current != target:  # skip when forcing or no-op
        accumulated_warnings: list[str] = []
        accumulated_blockers: list[str] = []
        for pf in iter_preflights():
            result = pf.check(scope, current, target)
            accumulated_warnings.extend(result.warnings)
            accumulated_blockers.extend(result.blockers)
        if strict:
            accumulated_blockers.extend(accumulated_warnings)
            accumulated_warnings = []
        if accumulated_blockers:
            for b in accumulated_blockers:
                out.error(f"preflight blocker: {b}", code=ErrorCode.PREFLIGHT_BLOCKED)
            out.fail(
                "phase transition blocked by preflight checks (use --force to override)",
                code=ErrorCode.PREFLIGHT_BLOCKED,
            )
        if accumulated_warnings:
            for w in accumulated_warnings:
                out.warn(f"preflight: {w}")
            confirm_destructive(
                f"Continue with phase {current} -> {target}? (use --strict to block on warnings)",
                yes=yes,
            )

    if dry_run:
        log = OpLog()
        log.modify_file(path, diff=f"{current} → {target}")
        if not no_decision:
            today = date.today().isoformat()
            log.create_file(scope.decisions_dir / f"{today}-phase-{target}.md", size=0)
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
        _decisions_dir = scope.decisions_dir
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

    # Fire phase transition hooks
    fire_phase_transition(scope, current, target, out=out)

    out.result(
        {
            "scope": "deliverable" if deliverable else "project",
            "name": f"{project}/{deliverable}" if deliverable else project,
            "phase": target,
            "transitioned_from": current,
        },
        human_text=f"Phase: {current} → {target}",
    )
