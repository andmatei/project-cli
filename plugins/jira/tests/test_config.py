"""Tests for JiraConfig."""

import pytest
from pydantic import ValidationError

from keel_jira.config import JiraConfig, JiraCredentialsMissing


def _minimal(**overrides):
    base = {"url": "https://acme.atlassian.net", "project_key": "PROJ"}
    base.update(overrides)
    return base


def test_minimal_config_with_env(jira_env) -> None:
    cfg = JiraConfig.from_extension_block(_minimal())
    assert cfg.url == "https://acme.atlassian.net"
    assert cfg.project_key == "PROJ"
    assert cfg.email == "test@example.com"
    assert cfg.token == "test-token"


def test_url_strips_trailing_slash(jira_env) -> None:
    cfg = JiraConfig.from_extension_block(_minimal(url="https://acme.atlassian.net/"))
    assert cfg.url == "https://acme.atlassian.net"


def test_url_must_have_scheme(jira_env) -> None:
    with pytest.raises(ValidationError):
        JiraConfig.from_extension_block(_minimal(url="acme.atlassian.net"))


def test_credentials_missing_raises(monkeypatch) -> None:
    monkeypatch.delenv("KEEL_JIRA_EMAIL", raising=False)
    monkeypatch.delenv("KEEL_JIRA_TOKEN", raising=False)
    with pytest.raises(JiraCredentialsMissing):
        JiraConfig.from_extension_block(_minimal())


def test_default_status_map(jira_env) -> None:
    cfg = JiraConfig.from_extension_block(_minimal())
    assert cfg.status_map == {
        "planned": "To Do",
        "active": "In Progress",
        "done": "Done",
        "cancelled": "Cancelled",
    }


def test_custom_status_map(jira_env) -> None:
    cfg = JiraConfig.from_extension_block(
        _minimal(
            status_map={
                "planned": "Backlog",
                "active": "Selected for Dev",
                "done": "Released",
                "cancelled": "Won't Do",
            }
        )
    )
    assert cfg.jira_status_for("planned") == "Backlog"
    assert cfg.jira_status_for("done") == "Released"


def test_status_map_must_cover_all_neutral_states(jira_env) -> None:
    with pytest.raises(ValidationError):
        JiraConfig.from_extension_block(_minimal(status_map={"planned": "To Do"}))


def test_jira_status_for_unknown_state_raises(jira_env) -> None:
    cfg = JiraConfig.from_extension_block(_minimal())
    with pytest.raises(KeyError):
        cfg.jira_status_for("ghost")


def test_extra_field_rejected(jira_env) -> None:
    with pytest.raises(ValidationError):
        JiraConfig.from_extension_block(_minimal(unexpected_field="x"))


def test_custom_issue_types(jira_env) -> None:
    cfg = JiraConfig.from_extension_block(
        _minimal(issue_type_milestone="Epic", issue_type_task="Story")
    )
    assert cfg.issue_type_milestone == "Epic"
    assert cfg.issue_type_task == "Story"
