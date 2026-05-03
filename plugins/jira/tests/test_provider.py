"""Tests for JiraProvider — the TicketProvider implementation."""

import pytest
import respx
from httpx import Response
from keel.api import Ticket, TicketProvider

from keel_jira.client import JiraAPIError
from keel_jira.config import JiraCredentialsMissing
from keel_jira.provider import JiraProvider


def _config_block(**overrides):
    base = {"url": "https://acme.atlassian.net", "project_key": "PROJ"}
    base.update(overrides)
    return base


def _configured_provider(jira_env, **config_overrides):
    p = JiraProvider()
    p.configure(_config_block(**config_overrides))
    return p


def test_provider_satisfies_protocol(jira_env) -> None:
    p = _configured_provider(jira_env)
    assert isinstance(p, TicketProvider)
    assert p.name == "jira"


def test_unconfigured_provider_raises(jira_env) -> None:
    p = JiraProvider()
    with pytest.raises(JiraCredentialsMissing):
        p.create_milestone("EPIC-1", "x", "")


def test_configure_requires_credentials(monkeypatch) -> None:
    monkeypatch.delenv("KEEL_JIRA_EMAIL", raising=False)
    monkeypatch.delenv("KEEL_JIRA_TOKEN", raising=False)
    p = JiraProvider()
    with pytest.raises(JiraCredentialsMissing):
        p.configure(_config_block())


def test_create_milestone(jira_env) -> None:
    p = _configured_provider(jira_env)
    with respx.mock:
        route = respx.post("https://acme.atlassian.net/rest/api/3/issue").mock(
            return_value=Response(201, json={"id": "1", "key": "PROJ-10"})
        )
        ticket = p.create_milestone("EPIC-1", "Foundation", "scope")
    assert isinstance(ticket, Ticket)
    assert ticket.id == "PROJ-10"
    assert ticket.url == "https://acme.atlassian.net/browse/PROJ-10"
    assert ticket.title == "Foundation"
    assert ticket.status == "To Do"

    import json as _json

    payload = _json.loads(route.calls.last.request.read())
    assert payload["fields"]["issuetype"]["name"] == "Story"
    assert payload["fields"]["parent"] == {"key": "EPIC-1"}


def test_create_milestone_no_parent(jira_env) -> None:
    p = _configured_provider(jira_env)
    with respx.mock:
        route = respx.post("https://acme.atlassian.net/rest/api/3/issue").mock(
            return_value=Response(201, json={"id": "1", "key": "PROJ-11"})
        )
        p.create_milestone("", "Foundation", "")
    import json as _json

    payload = _json.loads(route.calls.last.request.read())
    assert "parent" not in payload["fields"]


def test_create_task(jira_env) -> None:
    p = _configured_provider(jira_env)
    with respx.mock:
        respx.post("https://acme.atlassian.net/rest/api/3/issue").mock(
            return_value=Response(201, json={"id": "2", "key": "PROJ-20"})
        )
        ticket = p.create_task("PROJ-10", "Set up", "")
    assert ticket.id == "PROJ-20"


def test_transition_finds_correct_id(jira_env) -> None:
    p = _configured_provider(jira_env)
    with respx.mock:
        respx.get("https://acme.atlassian.net/rest/api/3/issue/PROJ-10/transitions").mock(
            return_value=Response(
                200,
                json={
                    "transitions": [
                        {"id": "11", "to": {"name": "In Progress"}},
                        {"id": "21", "to": {"name": "Done"}},
                    ]
                },
            )
        )
        route = respx.post("https://acme.atlassian.net/rest/api/3/issue/PROJ-10/transitions").mock(
            return_value=Response(204)
        )
        p.transition("PROJ-10", "done")
    import json as _json

    payload = _json.loads(route.calls.last.request.read())
    assert payload == {"transition": {"id": "21"}}


def test_transition_uses_status_map(jira_env) -> None:
    p = _configured_provider(
        jira_env,
        status_map={
            "planned": "Backlog",
            "active": "Selected for Dev",
            "done": "Released",
            "cancelled": "Won't Do",
        },
    )
    with respx.mock:
        respx.get("https://acme.atlassian.net/rest/api/3/issue/PROJ-10/transitions").mock(
            return_value=Response(
                200,
                json={"transitions": [{"id": "31", "to": {"name": "Released"}}]},
            )
        )
        route = respx.post("https://acme.atlassian.net/rest/api/3/issue/PROJ-10/transitions").mock(
            return_value=Response(204)
        )
        p.transition("PROJ-10", "done")
    import json as _json

    payload = _json.loads(route.calls.last.request.read())
    assert payload == {"transition": {"id": "31"}}


def test_transition_status_match_is_case_insensitive(jira_env) -> None:
    p = _configured_provider(jira_env)
    with respx.mock:
        respx.get("https://acme.atlassian.net/rest/api/3/issue/PROJ-10/transitions").mock(
            return_value=Response(
                200,
                json={"transitions": [{"id": "21", "to": {"name": "DONE"}}]},
            )
        )
        respx.post("https://acme.atlassian.net/rest/api/3/issue/PROJ-10/transitions").mock(
            return_value=Response(204)
        )
        p.transition("PROJ-10", "done")  # status_map has "Done", API has "DONE"


def test_transition_no_matching_transition_raises(jira_env) -> None:
    p = _configured_provider(jira_env)
    with respx.mock:
        respx.get("https://acme.atlassian.net/rest/api/3/issue/PROJ-10/transitions").mock(
            return_value=Response(
                200,
                json={"transitions": [{"id": "11", "to": {"name": "In Progress"}}]},
            )
        )
        with pytest.raises(JiraAPIError) as exc:
            p.transition("PROJ-10", "done")
    assert "Done" in str(exc.value)


def test_fetch(jira_env) -> None:
    p = _configured_provider(jira_env)
    with respx.mock:
        respx.get("https://acme.atlassian.net/rest/api/3/issue/PROJ-10").mock(
            return_value=Response(
                200,
                json={
                    "key": "PROJ-10",
                    "fields": {"summary": "Foundation", "status": {"name": "In Progress"}},
                },
            )
        )
        ticket = p.fetch("PROJ-10")
    assert ticket.id == "PROJ-10"
    assert ticket.title == "Foundation"
    assert ticket.status == "In Progress"
    assert ticket.url == "https://acme.atlassian.net/browse/PROJ-10"


def test_link_url_no_network(jira_env) -> None:
    p = _configured_provider(jira_env)
    # No respx — must not call out.
    assert p.link_url("PROJ-99") == "https://acme.atlassian.net/browse/PROJ-99"
