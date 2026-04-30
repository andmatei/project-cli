"""Tests for DAG helpers in keel.milestones."""
import pytest

from keel.manifest import Milestone, MilestonesManifest, Task
from keel.milestones import (
    GraphError,
    blocked_tasks,
    ready_tasks,
    topological_sort,
    validate_dag,
)


def _manifest(milestones, tasks):
    return MilestonesManifest(milestones=milestones, tasks=tasks)


def test_validate_dag_clean() -> None:
    m = _manifest(
        [Milestone(id="m1", title="x")],
        [
            Task(id="t1", milestone="m1", title="a"),
            Task(id="t2", milestone="m1", title="b", depends_on=["t1"]),
        ],
    )
    validate_dag(m)  # no exception


def test_validate_dag_unknown_milestone_ref() -> None:
    m = _manifest([], [Task(id="t1", milestone="ghost", title="x")])
    with pytest.raises(GraphError) as exc:
        validate_dag(m)
    assert "ghost" in str(exc.value)


def test_validate_dag_unknown_dep_ref() -> None:
    m = _manifest(
        [Milestone(id="m1", title="x")],
        [Task(id="t1", milestone="m1", title="x", depends_on=["nonexistent"])],
    )
    with pytest.raises(GraphError):
        validate_dag(m)


def test_validate_dag_cycle() -> None:
    m = _manifest(
        [Milestone(id="m1", title="x")],
        [
            Task(id="t1", milestone="m1", title="a", depends_on=["t2"]),
            Task(id="t2", milestone="m1", title="b", depends_on=["t1"]),
        ],
    )
    with pytest.raises(GraphError) as exc:
        validate_dag(m)
    assert "cycle" in str(exc.value).lower()


def test_ready_tasks() -> None:
    """Tasks with status=planned and all deps done are ready."""
    m = _manifest(
        [Milestone(id="m1", title="x")],
        [
            Task(id="t1", milestone="m1", title="a", status="done"),
            Task(id="t2", milestone="m1", title="b", depends_on=["t1"], status="planned"),
            Task(id="t3", milestone="m1", title="c", depends_on=["t1"], status="planned"),
            Task(id="t4", milestone="m1", title="d", depends_on=["t2"], status="planned"),
        ],
    )
    ready = ready_tasks(m)
    assert {t.id for t in ready} == {"t2", "t3"}


def test_blocked_tasks() -> None:
    m = _manifest(
        [Milestone(id="m1", title="x")],
        [
            Task(id="t1", milestone="m1", title="a", status="planned"),
            Task(id="t2", milestone="m1", title="b", depends_on=["t1"], status="planned"),
        ],
    )
    blocked = blocked_tasks(m)
    assert {t.id for t in blocked} == {"t2"}


def test_topological_sort() -> None:
    m = _manifest(
        [Milestone(id="m1", title="x")],
        [
            Task(id="t1", milestone="m1", title="a"),
            Task(id="t2", milestone="m1", title="b", depends_on=["t1"]),
            Task(id="t3", milestone="m1", title="c", depends_on=["t1"]),
            Task(id="t4", milestone="m1", title="d", depends_on=["t2", "t3"]),
        ],
    )
    order = [t.id for t in topological_sort(m)]
    # t1 comes before t2 and t3; t2 and t3 come before t4
    assert order.index("t1") < order.index("t2")
    assert order.index("t1") < order.index("t3")
    assert order.index("t2") < order.index("t4")
    assert order.index("t3") < order.index("t4")
