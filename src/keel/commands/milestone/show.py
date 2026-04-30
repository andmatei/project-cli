"""`keel milestone show <id>`."""

from __future__ import annotations

from collections import Counter

import typer

from keel.api import ErrorCode, Output, find_milestone, load_milestones_manifest
from keel.workspace import resolve_cli_scope


def cmd_show(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable", help="Scope: deliverable."),
    project: str | None = typer.Option(None, "--project", "-p", help="Project name."),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Show a milestone's metadata, status, fan-out, and task breakdown."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    manifest = load_milestones_manifest(scope.milestones_manifest_path)

    milestone = find_milestone(manifest, id)
    if milestone is None:
        out.fail(f"no milestone with id '{id}'", code=ErrorCode.NOT_FOUND)

    tasks = [t for t in manifest.tasks if t.milestone == id]
    by_status = Counter(t.status for t in tasks)

    payload = {
        **milestone.model_dump(),
        "task_count": len(tasks),
        "task_status_breakdown": dict(by_status),
    }

    if json_mode:
        out.result(payload)
        return

    lines = [
        f"Milestone: {milestone.id}",
        f"Title: {milestone.title}",
        f"Status: {milestone.status}",
    ]
    if milestone.description:
        lines.append(f"Description: {milestone.description}")
    if milestone.fan_out:
        lines.append(f"Fan-out: {', '.join(milestone.fan_out)}")
    if milestone.parent:
        lines.append(f"Parent: {milestone.parent}")
    if milestone.jira_id:
        lines.append(f"Ticket: {milestone.jira_id}")
    lines.append(f"Tasks: {len(tasks)}")
    if by_status:
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
        lines.append(f"  by status: {breakdown}")

    out.result(payload, human_text="\n".join(lines))
