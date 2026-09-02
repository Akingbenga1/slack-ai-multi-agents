"""Tests for Slack Socket Mode transport wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.app.settings import Settings
from api.app.slack import socket_mode as sm


def test_settings_socket_mode_enabled():
    off = Settings(slack_events_transport="http", slack_app_token="xapp-1")
    assert off.slack_socket_mode_enabled() is False

    on = Settings(slack_events_transport="socket", slack_app_token="xapp-1")
    assert on.slack_socket_mode_enabled() is True

    missing = Settings(slack_events_transport="socket", slack_app_token="")
    assert missing.slack_socket_mode_enabled() is False


@patch("api.app.slack.socket_mode.build_socket_mode_app")
def test_runner_start_stop(mock_build: MagicMock):
    mock_app = MagicMock()
    mock_build.return_value = mock_app
    mock_handler = MagicMock()
    settings = Settings(
        slack_events_transport="socket",
        slack_app_token="xapp-test-token",
    )

    with patch.object(sm, "SocketModeHandler", return_value=mock_handler) as mock_cls:
        runner = sm.SlackSocketModeRunner(settings)
        runner.start()
        mock_cls.assert_called_once_with(mock_app, "xapp-test-token")
        mock_handler.connect.assert_called_once()
        assert runner.running is True

        runner.stop()
        mock_handler.close.assert_called_once()


def test_start_socket_mode_noop_for_http_transport():
    sm.stop_socket_mode()
    result = sm.start_socket_mode(Settings(slack_events_transport="http"))
    assert result is None


def test_socket_mode_status_defaults():
    sm.stop_socket_mode()
    with patch.object(sm, "get_settings", return_value=Settings(slack_events_transport="http")):
        status = sm.socket_mode_status()
    assert status["transport"] == "http"
    assert status["running"] is False
