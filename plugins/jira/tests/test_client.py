"""Tests for JiraClient (httpx wrapper) using respx for HTTP mocking."""

import pytest
import respx
from httpx import Response

from keel_jira.client import JiraAPIError, JiraClient


@pytest.fixture
def client():
    c = JiraClient(url="https://acme.atlassian.net", email="t@t", token="tok")
    yield c
    c.close()


def test_create_issue_minimal(client) -> None:
    with respx.mock:
        route = respx.post("https://acme.atlassian.net/rest/api/3/issue").mock(
            return_value=Response(201, json={"id": "10001", "key": "PROJ-1"})
        )
        result = client.create_issue(project_key="PROJ", issue_type="Story", summary="Foundation")
    assert result == {"id": "10001", "key": "PROJ-1"}
    body = route.calls.last.request.read()
    import json as _json

    payload = _json.loads(body)
    assert payload["fields"]["project"]["key"] == "PROJ"
    assert payload["fields"]["issuetype"]["name"] == "Story"
    assert payload["fields"]["summary"] == "Foundation"
    assert "description" not in payload["fields"]
    assert "parent" not in payload["fields"]


def test_create_issue_with_description_and_parent(client) -> None:
    with respx.mock:
        route = respx.post("https://acme.atlassian.net/rest/api/3/issue").mock(
            return_value=Response(201, json={"id": "10002", "key": "PROJ-2"})
        )
        client.create_issue(
            project_key="PROJ",
            issue_type="Sub-task",
            summary="t1",
            description="Set up CI",
            parent_key="PROJ-1",
        )
    import json as _json

    payload = _json.loads(route.calls.last.request.read())
    assert payload["fields"]["parent"] == {"key": "PROJ-1"}
    assert payload["fields"]["description"]["type"] == "doc"
    assert payload["fields"]["description"]["content"][0]["content"][0]["text"] == "Set up CI"


def test_create_issue_api_error(client) -> None:
    with respx.mock:
        respx.post("https://acme.atlassian.net/rest/api/3/issue").mock(
            return_value=Response(400, json={"errorMessages": ["bad project key"]})
        )
        with pytest.raises(JiraAPIError) as exc:
            client.create_issue(project_key="X", issue_type="Story", summary="x")
    assert exc.value.status_code == 400
    assert "bad project key" in str(exc.value)


def test_get_issue(client) -> None:
    with respx.mock:
        respx.get("https://acme.atlassian.net/rest/api/3/issue/PROJ-5").mock(
            return_value=Response(
                200,
                json={
                    "key": "PROJ-5",
                    "fields": {"summary": "Hello", "status": {"name": "In Progress"}},
                },
            )
        )
        result = client.get_issue("PROJ-5")
    assert result["key"] == "PROJ-5"
    assert result["fields"]["status"]["name"] == "In Progress"


def test_list_transitions(client) -> None:
    with respx.mock:
        respx.get("https://acme.atlassian.net/rest/api/3/issue/PROJ-5/transitions").mock(
            return_value=Response(
                200,
                json={
                    "transitions": [
                        {"id": "11", "name": "Start", "to": {"name": "In Progress"}},
                        {"id": "21", "name": "Done", "to": {"name": "Done"}},
                    ]
                },
            )
        )
        out = client.list_transitions("PROJ-5")
    assert len(out) == 2
    assert out[0]["id"] == "11"
    assert out[1]["to"]["name"] == "Done"


def test_list_transitions_empty(client) -> None:
    with respx.mock:
        respx.get("https://acme.atlassian.net/rest/api/3/issue/PROJ-5/transitions").mock(
            return_value=Response(200, json={})
        )
        assert client.list_transitions("PROJ-5") == []


def test_transition_issue(client) -> None:
    with respx.mock:
        route = respx.post("https://acme.atlassian.net/rest/api/3/issue/PROJ-5/transitions").mock(
            return_value=Response(204)
        )
        client.transition_issue("PROJ-5", "21")
    import json as _json

    payload = _json.loads(route.calls.last.request.read())
    assert payload == {"transition": {"id": "21"}}


def test_transition_issue_error(client) -> None:
    with respx.mock:
        respx.post("https://acme.atlassian.net/rest/api/3/issue/PROJ-5/transitions").mock(
            return_value=Response(400, json={"errorMessages": ["bad transition"]})
        )
        with pytest.raises(JiraAPIError):
            client.transition_issue("PROJ-5", "99")


def test_link_url() -> None:
    c = JiraClient(url="https://acme.atlassian.net/", email="t@t", token="tok")
    try:
        assert c.link_url("PROJ-1") == "https://acme.atlassian.net/browse/PROJ-1"
    finally:
        c.close()


def test_url_strips_trailing_slash() -> None:
    c = JiraClient(url="https://acme.atlassian.net/", email="t@t", token="tok")
    try:
        assert c.link_url("PROJ-1") == "https://acme.atlassian.net/browse/PROJ-1"
    finally:
        c.close()


def test_context_manager_closes() -> None:
    with JiraClient(url="https://acme.atlassian.net", email="t@t", token="tok") as c:
        assert isinstance(c, JiraClient)
