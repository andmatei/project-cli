"""Graph helpers for milestone + task DAG validation and queries."""

from __future__ import annotations

from keel.lifecycle import is_terminal_task_state
from keel.manifest import MilestonesManifest, Task


class GraphError(ValueError):
    """Raised when the milestone/task graph is malformed."""


def validate_dag(m: MilestonesManifest) -> None:
    """Validate that the milestone/task graph is well-formed.

    Checks:
    - Every task.milestone references an existing milestone id
    - Every depends_on entry references an existing task id
    - The dependency graph is acyclic
    """
    milestone_ids = {ms.id for ms in m.milestones}
    task_ids = {t.id for t in m.tasks}

    for t in m.tasks:
        if t.milestone not in milestone_ids:
            raise GraphError(f"task {t.id!r} references unknown milestone {t.milestone!r}")
        for dep in t.depends_on:
            if dep not in task_ids:
                raise GraphError(f"task {t.id!r} depends_on unknown task {dep!r}")

    # Check for cycles via DFS-based color marking.
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {tid: WHITE for tid in task_ids}
    deps: dict[str, list[str]] = {t.id: t.depends_on for t in m.tasks}

    def dfs(node: str, path: list[str]) -> None:
        if color[node] == GRAY:
            cycle_start = path.index(node)
            cycle = " -> ".join(path[cycle_start:] + [node])
            raise GraphError(f"cycle detected: {cycle}")
        if color[node] == BLACK:
            return
        color[node] = GRAY
        path.append(node)
        for dep in deps[node]:
            dfs(dep, path)
        path.pop()
        color[node] = BLACK

    for tid in task_ids:
        if color[tid] == WHITE:
            dfs(tid, [])


def ready_tasks(m: MilestonesManifest) -> list[Task]:
    """Tasks with status=planned and all dependencies in a terminal (done/cancelled) state."""
    by_id = {t.id: t for t in m.tasks}
    out: list[Task] = []
    for t in m.tasks:
        if t.status != "planned":
            continue
        if all(is_terminal_task_state(by_id[d].status) for d in t.depends_on if d in by_id):
            out.append(t)
    return out


def blocked_tasks(m: MilestonesManifest) -> list[Task]:
    """Tasks with status=planned but at least one dependency in a non-terminal state."""
    by_id = {t.id: t for t in m.tasks}
    out: list[Task] = []
    for t in m.tasks:
        if t.status != "planned":
            continue
        if any(not is_terminal_task_state(by_id[d].status) for d in t.depends_on if d in by_id):
            out.append(t)
    return out


def topological_sort(m: MilestonesManifest) -> list[Task]:
    """Return tasks in dependency order (deps first). Raises GraphError on cycle."""
    validate_dag(m)
    by_id = {t.id: t for t in m.tasks}
    in_degree: dict[str, int] = {t.id: 0 for t in m.tasks}
    for t in m.tasks:
        for dep in t.depends_on:
            if dep in in_degree:
                in_degree[t.id] += 1

    # Kahn's algorithm
    queue: list[str] = [tid for tid, d in in_degree.items() if d == 0]
    out: list[Task] = []
    while queue:
        # Stable order: take the lexically-first ready task each step
        queue.sort()
        tid = queue.pop(0)
        out.append(by_id[tid])
        for t in m.tasks:
            if tid in t.depends_on:
                in_degree[t.id] -= 1
                if in_degree[t.id] == 0:
                    queue.append(t.id)
    return out
