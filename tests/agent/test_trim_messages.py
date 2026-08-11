"""Unit tests for checkpoint message trim helper."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from api.app.agent.nodes.trim import trim_checkpoint_messages


def test_trim_checkpoint_messages_noop_under_cap():
    msgs = [HumanMessage(content="a"), AIMessage(content="b")]
    assert trim_checkpoint_messages(msgs, max_messages=10) is None


def test_trim_checkpoint_messages_keeps_tail():
    msgs = [HumanMessage(content=str(i)) for i in range(10)]
    update = trim_checkpoint_messages(msgs, max_messages=4)
    assert update is not None
    assert update[0].id == REMOVE_ALL_MESSAGES
    assert len(update) == 5  # remove + 4 kept
    assert [m.content for m in update[1:]] == ["6", "7", "8", "9"]
