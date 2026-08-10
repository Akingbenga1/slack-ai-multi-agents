"""Route node — classify workflow + seed model tier.

Classification lives in ``api.app.agent.workflows`` (ordered Strategy rules).
This module stays a thin LangGraph node + back-compat re-exports.
"""

from __future__ import annotations

from typing import Any

from api.app.agent.guardrails import require_tenant_client_id
from api.app.agent.llm import message_content
from api.app.agent.policy import choose_model_tier, detect_complexity_flags
from api.app.agent.state import AgentState
from api.app.agent.workflows import (
    classify_workflow,
    question_requests_workflow_advice,
)
from api.app.logging_config import get_logger

logger = get_logger("api.agent.nodes.route")

# Back-compat re-exports (tests / Slack imported these from route)
__all__ = [
    "classify_workflow",
    "question_requests_workflow_advice",
    "route_node",
]


def route_node(state: AgentState) -> dict[str, Any]:
    """Set workflow, question, complexity_flags, and initial model_tier."""
    client_id = require_tenant_client_id(state.get("client_id"), where="route")

    question = (state.get("question") or "").strip()
    if not question:
        messages = state.get("messages") or []
        for msg in reversed(messages):
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "type", None)
            # LangChain HumanMessage.type == "human"; dict uses role=user
            if role in ("user", "human") or getattr(msg, "type", None) == "human":
                question = message_content(msg).strip()
                break

    has_attachments = bool(state.get("attached_evidence"))
    workflow = classify_workflow(question, has_attachments=has_attachments)
    flags = detect_complexity_flags(question, workflow=workflow)
    tier = choose_model_tier(flags=flags)

    logger.info(
        "agent_route client_id=%s workflow=%s model_tier=%s flags=%s attachments=%s",
        client_id,
        workflow,
        tier,
        flags,
        len(state.get("attached_evidence") or []),
    )
    return {
        "client_id": client_id,
        "question": question,
        "workflow": workflow,
        "complexity_flags": flags,
        "model_tier": tier,
        "retrieved_chunks": state.get("retrieved_chunks") or [],
        "attached_evidence": list(state.get("attached_evidence") or []),
    }
