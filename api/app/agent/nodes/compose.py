"""Compose node — grounded answer from evidence + model tier."""

from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import UUID

from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

from api.app.agent.chunks import format_evidence
from api.app.agent.guardrails import (
    HEDGE_MESSAGE,
    filter_chunks_for_tenant,
    require_tenant_client_id,
    should_hedge,
)
from api.app.agent.llm import ChatModel, get_chat_model
from api.app.agent.policy import choose_model_tier
from api.app.agent.prompts import build_compose_user_prompt, system_prompt_for
from api.app.agent.state import AgentState, ModelTier
from api.app.governance.usage import EVENT_LLM_TOKENS, record_usage
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings
from mcp_server.tools.onboarding import ONBOARDING_NOT_CONFIGURED_MESSAGE

logger = get_logger("api.agent.nodes.compose")

# Back-compat alias (tests / callers that inject a fixed system prompt)
DEFAULT_SYSTEM = system_prompt_for("qa")


def make_compose_node(
    *,
    settings: Settings | None = None,
    chat_model: Optional[ChatModel] = None,
    db_factory: Optional[Callable[[], Session]] = None,
    system_prompt: str | None = None,
) -> Callable[[AgentState], dict[str, Any]]:
    """Build compose node; optional db_factory records llm_tokens usage."""

    settings = settings or get_settings()
    model = chat_model or get_chat_model(settings)
    # When set, overrides workflow-specific prompts (tests / dry-run inject)
    fixed_system = system_prompt

    def compose_node(state: AgentState) -> dict[str, Any]:
        client_id = require_tenant_client_id(
            state.get("client_id"),
            where="compose",
        )

        flags = list(state.get("complexity_flags") or [])
        tier: ModelTier = state.get("model_tier") or choose_model_tier(flags=flags)
        chunks = filter_chunks_for_tenant(
            list(state.get("retrieved_chunks") or []),
            client_id,
            min_score=float(settings.agent_min_score),
        )
        question = (state.get("question") or "").strip() or "(no question)"
        workflow = state.get("workflow") or "qa"
        hedge = bool(state.get("hedge")) or should_hedge(chunks)

        # Onboarding stub: deterministic “not configured” (no LLM, no RAG hedge)
        if workflow == "onboarding":
            message = (
                (state.get("meeting_draft") or "").strip()
                or ONBOARDING_NOT_CONFIGURED_MESSAGE
            )
            logger.info(
                "agent_compose_onboarding_stub client_id=%s tier=%s",
                client_id,
                tier,
            )
            return {
                "client_id": client_id,
                "model_tier": tier,
                "retrieved_chunks": chunks,
                "answer": message,
                "usage_tokens": 0,
                "hedge": False,
                "messages": [AIMessage(content=message)],
            }

        # Hard hedge: no LLM call when we lack tenant-scoped evidence
        if hedge:
            logger.info(
                "agent_compose_hedge client_id=%s tier=%s reason=no_evidence",
                client_id,
                tier,
            )
            return {
                "client_id": client_id,
                "model_tier": tier,
                "retrieved_chunks": chunks,
                "answer": HEDGE_MESSAGE,
                "usage_tokens": 0,
                "hedge": True,
                "messages": [AIMessage(content=HEDGE_MESSAGE)],
            }

        evidence = format_evidence(chunks)
        user_prompt = build_compose_user_prompt(
            workflow=workflow,
            question=question,
            evidence=evidence,
            meeting_draft=state.get("meeting_draft"),
            report_window=state.get("report_window"),
        )
        system = fixed_system if fixed_system is not None else system_prompt_for(workflow)
        org_overlay = (state.get("org_system_prompt") or "").strip()
        if org_overlay and fixed_system is None:
            system = f"{org_overlay}\n\n{system}"

        result = model.complete(
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
            model_tier=tier,
        )

        if db_factory is not None and result.total_tokens > 0:
            try:
                db = db_factory()
                try:
                    record_usage(
                        db,
                        UUID(str(client_id)),
                        EVENT_LLM_TOKENS,
                        units=result.total_tokens,
                        meta={
                            "model": result.model,
                            "model_tier": tier,
                            "input_tokens": result.input_tokens,
                            "output_tokens": result.output_tokens,
                            "workflow": state.get("workflow"),
                        },
                        commit=True,
                    )
                finally:
                    db.close()
            except Exception:
                logger.exception(
                    "agent_usage_record_failed client_id=%s tokens=%s",
                    client_id,
                    result.total_tokens,
                )

        logger.info(
            "agent_compose client_id=%s workflow=%s tier=%s model=%s tokens=%s hedge=%s",
            client_id,
            workflow,
            tier,
            result.model,
            result.total_tokens,
            hedge,
        )
        return {
            "client_id": client_id,
            "model_tier": tier,
            "retrieved_chunks": chunks,
            "answer": result.text,
            "usage_tokens": result.total_tokens,
            "hedge": False,
            "messages": [AIMessage(content=result.text)],
        }

    return compose_node
