"""Child-process environment policy."""

from __future__ import annotations

import os

from api.app.agent.sandbox import child_environment
from api.app.settings import Settings


def test_child_environment_drops_secret_names(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-value")
    monkeypatch.setenv("JWT_SECRET", "another")
    monkeypatch.setenv("PATH", os.environ.get("PATH", "C:\\Windows"))
    env = child_environment(Settings(executor_scrub_child_env=True))
    assert "ANTHROPIC_API_KEY" not in env
    assert "JWT_SECRET" not in env
    assert "PATH" in env


def test_child_environment_can_keep_host_env(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-value")
    env = child_environment(Settings(executor_scrub_child_env=False))
    assert env.get("ANTHROPIC_API_KEY") == "secret-value"
