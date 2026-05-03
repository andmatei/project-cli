"""Shared pytest fixtures for keel-jira tests."""

import pytest


@pytest.fixture
def jira_env(monkeypatch):
    """Set the credential env vars to dummy values."""
    monkeypatch.setenv("KEEL_JIRA_EMAIL", "test@example.com")
    monkeypatch.setenv("KEEL_JIRA_TOKEN", "test-token")
