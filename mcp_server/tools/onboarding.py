"""MCP tool: ``start_onboarding`` — honest stub (process not configured)."""

from __future__ import annotations

from typing import Any

from api.app.qdrant.tenant import require_client_id

# Shared copy — agent compose falls back to the same string if MCP payload is empty.
ONBOARDING_NOT_CONFIGURED_MESSAGE = (
    "Client onboarding is not configured for this workspace yet. "
    "A guided checklist process will be added in a later phase — "
    "there is no onboarding workflow to start today."
)


def start_onboarding(
    *,
    client_id: str | None,
) -> dict[str, Any]:
    """
    Stub entry for a future onboarding checklist state machine.

    Always reports ``configured=false`` with a clear message. Does not invent
    steps, gather fields, or call retrieval.
    """
    cid = require_client_id(client_id)
    message = ONBOARDING_NOT_CONFIGURED_MESSAGE
    return {
        "client_id": cid,
        "configured": False,
        "status": "not_configured",
        "message": message,
        "markdown": message,
        "note": (
            "Onboarding process is deferred (stub only). "
            "See docs/onboarding.md for the future extension point."
        ),
    }


__all__ = [
    "ONBOARDING_NOT_CONFIGURED_MESSAGE",
    "start_onboarding",
]
