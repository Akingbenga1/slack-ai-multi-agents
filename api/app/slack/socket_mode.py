"""Slack Socket Mode transport — Bolt listener wired to shared event dispatch."""

from __future__ import annotations

import threading
from typing import Any

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.authorization import AuthorizeResult
from sqlalchemy.orm import Session

from api.app.db.session import SessionLocal
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings
from api.app.slack.event_dispatch import dispatch_events_api_payload
from api.app.slack.store import get_bot_token, get_install_by_team

logger = get_logger("api.slack.socket_mode")

_runner: "SlackSocketModeRunner | None" = None
_runner_lock = threading.Lock()


def _authorize(
    *,
    enterprise_id: str | None,
    team_id: str | None,
    user_id: str | None,
    client: Any,
    settings: Settings,
) -> AuthorizeResult:
    """Resolve per-workspace bot token from the install store (multi-tenant)."""
    _ = (enterprise_id, user_id, client)
    tid = (team_id or "").strip()
    if not tid:
        raise RuntimeError("missing team_id for Slack authorize")

    db = SessionLocal()
    try:
        install = get_install_by_team(db, tid)
        if install is None:
            raise RuntimeError(f"no Slack install for team_id={tid}")
        token = get_bot_token(install, settings)
    finally:
        db.close()

    return AuthorizeResult(
        enterprise_id=enterprise_id,
        team_id=tid,
        bot_token=token,
    )


def build_socket_mode_app(settings: Settings) -> App:
    """Construct a Bolt app that authorizes tokens from the install store."""
    signing_secret = (settings.slack_signing_secret or "").strip() or None

    def authorize(**kwargs: Any) -> AuthorizeResult:
        return _authorize(settings=settings, **kwargs)

    app = App(
        signing_secret=signing_secret,
        authorize=authorize,
        process_before_response=False,
    )

    @app.event("app_mention")
    def on_app_mention(event: dict[str, Any], body: dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            dispatch_events_api_payload(
                body,
                settings=settings,
                db=db,
            )
        finally:
            db.close()

    @app.event("message")
    def on_message(event: dict[str, Any], body: dict[str, Any]) -> None:
        # DM subscription delivers type=message; channel chatter is filtered in dispatch.
        db = SessionLocal()
        try:
            dispatch_events_api_payload(
                body,
                settings=settings,
                db=db,
            )
        finally:
            db.close()

    return app


class SlackSocketModeRunner:
    """Background Socket Mode listener."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._app = build_socket_mode_app(settings)
        self._handler: SocketModeHandler | None = None

    @property
    def running(self) -> bool:
        return self._handler is not None

    def start(self) -> None:
        app_token = (self._settings.slack_app_token or "").strip()
        if not app_token:
            raise RuntimeError("SLACK_APP_TOKEN is required for Socket Mode")

        self._handler = SocketModeHandler(self._app, app_token)
        # connect() is non-blocking and safe from FastAPI lifespan (Windows-safe).
        self._handler.connect()
        logger.info("slack_socket_mode_started")

    def stop(self) -> None:
        if self._handler is not None:
            try:
                self._handler.close()
            except Exception:
                logger.exception("slack_socket_mode_close_failed")
            self._handler = None
        logger.info("slack_socket_mode_stopped")


def start_socket_mode(settings: Settings | None = None) -> SlackSocketModeRunner | None:
    """Start Socket Mode when transport is configured; idempotent."""
    global _runner
    settings = settings or get_settings()
    if settings.slack_events_transport != "socket":
        return None

    with _runner_lock:
        if _runner is not None and _runner.running:
            return _runner
        _runner = SlackSocketModeRunner(settings)
        _runner.start()
        return _runner


def stop_socket_mode() -> None:
    """Stop the background Socket Mode listener if running."""
    global _runner
    with _runner_lock:
        if _runner is None:
            return
        _runner.stop()
        _runner = None


def socket_mode_status() -> dict[str, Any]:
    """Lightweight status for health/debug."""
    settings = get_settings()
    return {
        "transport": settings.slack_events_transport,
        "configured": settings.slack_socket_mode_enabled(),
        "running": _runner.running if _runner is not None else False,
    }
