"""`keel task graph` — ASCII tree, Graphviz DOT, or JSON dump of the task DAG."""

from __future__ import annotations

import typer

from keel.errors import ErrorCode
from keel.manifest import MilestonesManifest, Task, load_milestones_manifest
from keel.milestones import blocked_tasks, ready_tasks, topological_sort
from keel.output import Output
from keel.workspace import resolve_cli_scope


def _filter_by_milestone(manifest: MilestonesManifest, milestone: str | None) -> MilestonesManifest:
    if milestone is None:
        return manifest
    filtered_tasks = [t for t in manifest.tasks if t.milestone == milestone]
    filtered_milestones = [m for m in manifest.milestones if m.id == milestone]
    return MilestonesManifest(milestones=filtered_milestones, tasks=filtered_tasks)


def _render_ascii(manifest: MilestonesManifest, ready_ids: set[str]) -> str:
    """Render an indented tree showing each task and its direct dependencies."""
    if not manifest.tasks:
        return "(no tasks)"
    # Roots: tasks with no dependencies
    roots = [t for t in manifest.tasks if not t.depends_on]
    children: dict[str, list[Task]] = {}
    for t in manifest.tasks:
        for dep in t.depends_on:
            children.setdefault(dep, []).append(t)

    lines: list[str] = []
    seen: set[str] = set()

    def walk(t: Task, depth: int) -> None:
        marker = "*" if t.id in ready_ids else " "
        prefix = "  " * depth + ("- " if depth > 0 else "")
        lines.append(f"{prefix}[{marker}] {t.id} ({t.status}) — {t.title}")
        if t.id in seen:
            return
        seen.add(t.id)
        for child in sorted(children.get(t.id, []), key=lambda x: x.id):
            walk(child, depth + 1)

    for root in sorted(roots, key=lambda x: x.id):
        walk(root, 0)

    # Tasks not reachable from roots (shouldn't happen in a valid DAG, but defensive):
    unseen = [t for t in manifest.tasks if t.id not in seen]
    for t in sorted(unseen, key=lambda x: x.id):
        walk(t, 0)

    return "\n".join(lines)


def _render_dot(manifest: MilestonesManifest) -> str:
    lines = ["digraph tasks {", "  rankdir=LR;"]
    for t in manifest.tasks:
        label = f"{t.id}\\n{t.title}\\n[{t.status}]"
        lines.append(f'  "{t.id}" [label="{label}"];')
    for t in manifest.tasks:
        for dep in t.depends_on:
            lines.append(f'  "{dep}" -> "{t.id}";')
    lines.append("}")
    return "\n".join(lines)


def cmd_graph(
    ctx: typer.Context,
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    milestone: str | None = typer.Option(
        None, "--milestone", "-m", help="Limit to tasks in one milestone."
    ),
    dot: bool = typer.Option(False, "--dot", help="Emit Graphviz DOT format."),
    json_mode: bool = typer.Option(
        False, "--json", help="Emit JSON with topological order and ready/blocked flags."
    ),
) -> None:
    """Render the task dependency graph as ASCII (default), Graphviz DOT, or JSON."""
    out = Output.from_context(ctx, json_mode=json_mode)

    if dot and json_mode:
        out.fail("--dot and --json are mutually exclusive", code=ErrorCode.CONFLICTING_FLAGS, exit_code=2)

    scope = resolve_cli_scope(project, deliverable, out=out)
    manifest = load_milestones_manifest(scope.milestones_manifest_path)
    manifest = _filter_by_milestone(manifest, milestone)

    ready_ids = {t.id for t in ready_tasks(manifest)}
    blocked_ids = {t.id for t in blocked_tasks(manifest)}

    if json_mode:
        ordered = topological_sort(manifest)
        out.result(
            {
                "tasks": [
                    {
                        **t.model_dump(),
                        "ready": t.id in ready_ids,
                        "blocked": t.id in blocked_ids,
                    }
                    for t in ordered
                ]
            }
        )
        return

    if dot:
        print(_render_dot(manifest))
        return

    print(_render_ascii(manifest, ready_ids))
