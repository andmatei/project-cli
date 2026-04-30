"""Tests for the TicketProvider Protocol and Ticket dataclass."""

from keel.ticketing.base import Ticket, TicketProvider


def test_ticket_dataclass() -> None:
    t = Ticket(id="JIRA-1", url="https://example.com/JIRA-1")
    assert t.id == "JIRA-1"
    assert t.url == "https://example.com/JIRA-1"
    assert t.title is None
    assert t.status is None


def test_ticket_with_optionals() -> None:
    t = Ticket(id="X-1", url="u", title="Title", status="In Progress")
    assert t.title == "Title"
    assert t.status == "In Progress"


def test_ticket_is_frozen() -> None:
    import dataclasses

    t = Ticket(id="X-1", url="u")
    try:
        t.id = "Y-2"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Ticket should be frozen")


def test_ticket_provider_is_protocol() -> None:
    """TicketProvider should be a runtime-checkable Protocol."""
    # Any object with the right attributes/methods passes isinstance.
    class FakeProvider:
        name = "fake"

        def configure(self, config: dict) -> None:  # noqa: ARG002
            ...

        def create_milestone(self, parent_id, title, description) -> None:  # noqa: ARG002
            ...

        def create_task(self, parent_milestone_id, title, description) -> None:  # noqa: ARG002
            ...

        def transition(self, ticket_id, target_state) -> None:  # noqa: ARG002
            ...

        def fetch(self, ticket_id) -> None:  # noqa: ARG002
            ...

        def link_url(self, ticket_id) -> None:  # noqa: ARG002
            ...

    assert isinstance(FakeProvider(), TicketProvider)


# Task 4.2 tests
def test_load_provider_returns_none_when_not_found() -> None:
    from unittest.mock import patch

    from keel.ticketing.registry import load_provider

    with patch("keel.ticketing.registry.entry_points", return_value=[]):
        result = load_provider("nothing")
    assert result is None


def test_list_providers_empty() -> None:
    from unittest.mock import patch

    from keel.ticketing.registry import list_providers

    with patch("keel.ticketing.registry.entry_points", return_value=[]):
        result = list_providers()
    assert result == []


def test_load_provider_finds_registered() -> None:
    """When an entry point matches by name, load_provider instantiates it."""
    from unittest.mock import MagicMock, patch

    from keel.ticketing.registry import load_provider

    class Fake:
        name = "fake"

        def configure(self, config) -> None:  # noqa: ANN001, ARG002
            pass

        def create_milestone(self, parent_id, title, description) -> None:  # noqa: ANN001, ARG002
            pass

        def create_task(self, parent_milestone_id, title, description) -> None:  # noqa: ANN001, ARG002
            pass

        def transition(self, ticket_id, target_state) -> None:  # noqa: ANN001, ARG002
            pass

        def fetch(self, ticket_id) -> None:  # noqa: ANN001, ARG002
            pass

        def link_url(self, ticket_id) -> None:  # noqa: ANN001, ARG002
            pass

    fake_ep = MagicMock()
    fake_ep.name = "fake"
    fake_ep.load.return_value = Fake

    with patch("keel.ticketing.registry.entry_points", return_value=[fake_ep]):
        result = load_provider("fake")
    assert result is not None
    assert result.name == "fake"


def test_list_providers_returns_names() -> None:
    from unittest.mock import MagicMock, patch

    from keel.ticketing.registry import list_providers

    ep1 = MagicMock()
    ep1.name = "jira"
    ep2 = MagicMock()
    ep2.name = "github"
    with patch("keel.ticketing.registry.entry_points", return_value=[ep1, ep2]):
        result = list_providers()
    assert result == ["github", "jira"]  # sorted


# Task 4.3 tests
def test_mock_provider_satisfies_protocol() -> None:
    from keel.ticketing.base import TicketProvider
    from keel.ticketing.mock import MockProvider

    p = MockProvider()
    assert isinstance(p, TicketProvider)
    assert p.name == "mock"


def test_mock_provider_records_create_milestone() -> None:
    from keel.ticketing.mock import MockProvider

    p = MockProvider()
    t = p.create_milestone("EPIC-1", "Foundation", "")
    assert t.id.startswith("MOCK-")
    assert ("create_milestone", "EPIC-1", "Foundation", "") in p.calls


def test_mock_provider_records_create_task() -> None:
    from keel.ticketing.mock import MockProvider

    p = MockProvider()
    t = p.create_task("STORY-1", "Set up", "Initial config")
    assert t.id.startswith("MOCK-")
    assert ("create_task", "STORY-1", "Set up", "Initial config") in p.calls


def test_mock_provider_transition_recorded() -> None:
    from keel.ticketing.mock import MockProvider

    p = MockProvider()
    p.create_milestone("E-1", "x", "")
    ticket_id = "MOCK-1"
    p.transition(ticket_id, "active")
    assert ("transition", ticket_id, "active") in p.calls


def test_mock_provider_fetch_returns_recorded_ticket() -> None:
    from keel.ticketing.mock import MockProvider

    p = MockProvider()
    t = p.create_milestone("E-1", "x", "")
    fetched = p.fetch(t.id)
    assert fetched.id == t.id


def test_mock_provider_link_url() -> None:
    from keel.ticketing.mock import MockProvider

    p = MockProvider()
    url = p.link_url("MOCK-42")
    assert "MOCK-42" in url


# Task 4.4 tests
def test_get_provider_for_project_no_config(make_project) -> None:
    """No [extensions.ticketing] → returns None."""
    from keel.manifest import load_project_manifest
    from keel.ticketing import get_provider_for_project

    proj = make_project("foo")
    m = load_project_manifest(proj / "design" / "project.toml")
    assert get_provider_for_project(m) is None


def test_get_provider_for_project_unknown_provider(make_project) -> None:
    """[extensions.ticketing.provider] = "ghost" but no plugin installed → None."""
    from keel.manifest import (
        load_project_manifest,
        save_project_manifest,
    )
    from keel.ticketing import get_provider_for_project

    proj = make_project("foo")
    m = load_project_manifest(proj / "design" / "project.toml")
    m.extensions["ticketing"] = {"provider": "ghost"}
    save_project_manifest(proj / "design" / "project.toml", m)
    m2 = load_project_manifest(proj / "design" / "project.toml")
    assert get_provider_for_project(m2) is None


def test_get_provider_for_project_loads_and_configures(make_project) -> None:
    """Configured provider is loaded and `.configure()` is called with the provider's subsection."""
    from unittest.mock import patch

    from keel.manifest import (
        load_project_manifest,
        save_project_manifest,
    )
    from keel.ticketing import get_provider_for_project
    from keel.ticketing.mock import MockProvider

    proj = make_project("foo")
    m = load_project_manifest(proj / "design" / "project.toml")
    m.extensions["ticketing"] = {"provider": "mock", "mock": {"key": "value"}}
    save_project_manifest(proj / "design" / "project.toml", m)
    m2 = load_project_manifest(proj / "design" / "project.toml")

    # Patch load_provider to return a fresh MockProvider for "mock"
    fake = MockProvider()
    with patch("keel.ticketing.load_provider", return_value=fake):
        provider = get_provider_for_project(m2)
    assert provider is fake
    assert ("configure", {"key": "value"}) in fake.calls


# Task 4.5 tests
def test_milestone_add_pushes_to_provider(make_project, monkeypatch) -> None:
    """When ticketing is configured + provider available, milestone add records ticket id."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from keel.app import app
    from keel.manifest import (
        load_milestones_manifest,
        load_project_manifest,
        save_project_manifest,
    )
    from keel.ticketing.mock import MockProvider

    runner = CliRunner()
    proj = make_project("foo")
    m = load_project_manifest(proj / "design" / "project.toml")
    m.extensions["ticketing"] = {"provider": "mock", "parent_id": "EPIC-1"}
    save_project_manifest(proj / "design" / "project.toml", m)
    monkeypatch.chdir(proj / "design")

    fake = MockProvider()
    with patch("keel.ticketing.load_provider", return_value=fake):
        result = runner.invoke(app, ["milestone", "add", "m1", "--title", "X"], catch_exceptions=False)
    assert result.exit_code == 0
    saved = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert saved.milestones[0].ticket_id is not None
    assert saved.milestones[0].ticket_id.startswith("MOCK-")
    assert any(c[0] == "create_milestone" for c in fake.calls)


def test_milestone_add_no_push_skips_provider(make_project, monkeypatch) -> None:
    """--no-push skips the provider call even when configured."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from keel.app import app
    from keel.manifest import (
        load_milestones_manifest,
        load_project_manifest,
        save_project_manifest,
    )
    from keel.ticketing.mock import MockProvider

    runner = CliRunner()
    proj = make_project("foo")
    m = load_project_manifest(proj / "design" / "project.toml")
    m.extensions["ticketing"] = {"provider": "mock"}
    save_project_manifest(proj / "design" / "project.toml", m)
    monkeypatch.chdir(proj / "design")

    fake = MockProvider()
    with patch("keel.ticketing.load_provider", return_value=fake):
        result = runner.invoke(app, ["milestone", "add", "m1", "--title", "X", "--no-push"])
    assert result.exit_code == 0
    saved = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert saved.milestones[0].ticket_id is None
    assert not any(c[0] == "create_milestone" for c in fake.calls)


def test_task_add_pushes_with_parent_milestone_ticket_id(make_project, monkeypatch) -> None:
    from unittest.mock import patch

    from typer.testing import CliRunner

    from keel.app import app
    from keel.manifest import (
        load_milestones_manifest,
        load_project_manifest,
        save_project_manifest,
    )
    from keel.ticketing.mock import MockProvider

    runner = CliRunner()
    proj = make_project("foo")
    m = load_project_manifest(proj / "design" / "project.toml")
    m.extensions["ticketing"] = {"provider": "mock", "parent_id": "EPIC-1"}
    save_project_manifest(proj / "design" / "project.toml", m)
    monkeypatch.chdir(proj / "design")

    fake = MockProvider()
    with patch("keel.ticketing.load_provider", return_value=fake):
        runner.invoke(app, ["milestone", "add", "m1", "--title", "M"], catch_exceptions=False)
        # milestone now has ticket_id = MOCK-1 (or similar)
        result = runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "T"])
    assert result.exit_code == 0
    saved = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert saved.tasks[0].ticket_id is not None


def test_milestone_done_transitions_provider(make_project, monkeypatch) -> None:
    from unittest.mock import patch

    from typer.testing import CliRunner

    from keel.app import app
    from keel.manifest import load_project_manifest, save_project_manifest
    from keel.ticketing.mock import MockProvider

    runner = CliRunner()
    proj = make_project("foo")
    m = load_project_manifest(proj / "design" / "project.toml")
    m.extensions["ticketing"] = {"provider": "mock"}
    save_project_manifest(proj / "design" / "project.toml", m)
    monkeypatch.chdir(proj / "design")

    fake = MockProvider()
    with patch("keel.ticketing.load_provider", return_value=fake):
        runner.invoke(app, ["milestone", "add", "m1", "--title", "X"], catch_exceptions=False)
        runner.invoke(app, ["milestone", "start", "m1"])
        result = runner.invoke(app, ["milestone", "done", "m1"], catch_exceptions=False)
    assert result.exit_code == 0
    transitions = [c for c in fake.calls if c[0] == "transition"]
    assert any(args[2] == "done" for args in transitions)
