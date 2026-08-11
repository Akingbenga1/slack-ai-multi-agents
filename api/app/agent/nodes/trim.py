"""Trim checkpointed agent message history (bound memory / Postgres growth)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from api.app.agent.state import AgentState
from api.app.settings import Settings, get_settings


def trim_checkpoint_messages(
    messages: list[Any],
    *,
    max_messages: int,
) -> list[Any] | None:
    """
    Return a LangGraph messages update that keeps the last ``max_messages``,
    or ``None`` when no trim is needed.
    """
    cap = max(2, int(max_messages))
    if len(messages) <= cap:
        return None
    keep = list(messages[-cap:])
    return [RemoveMessage(id=REMOVE_ALL_MESSAGES), *keep]


def make_trim_messages_node(
    *,
    settings: Settings | None = None,
    max_messages: int | None = None,
):
    """Node: after compose, bound checkpointed ``messages`` growth."""

    settings = settings or get_settings()
    cap = (
        max_messages
        if max_messages is not None
        else int(getattr(settings, "agent_max_checkpoint_messages", 40) or 40)
    )

    def trim_messages_node(state: AgentState) -> dict[str, Any]:
        update = trim_checkpoint_messages(
            list(state.get("messages") or []),
            max_messages=cap,
        )
        if update is None:
            return {}
        return {"messages": update}

    return trim_messages_node


__all__ = ["make_trim_messages_node", "trim_checkpoint_messages"]
