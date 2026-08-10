"""LangGraph tool node — retrieval via bundled MCP client (Sprint 15.4+)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from api.app.agent.chunks import citation_to_chunk
from api.app.agent.guardrails import (
    filter_chunks_for_tenant,
    require_tenant_client_id,
    should_hedge,
)
from api.app.agent.mcp_client import (
    McpCallTool,
    citation_from_mcp_hit,
    draft_meeting_agenda_via_mcp,
    draft_meeting_brief_via_mcp,
    draft_meeting_notes_via_mcp,
    draft_report_via_mcp,
    search_knowledge_via_mcp,
    start_onboarding_via_mcp,
)
from api.app.agent.nodes.retrieve import SearchFn
from api.app.agent.state import AgentState
from api.app.logging_config import get_logger
from api.app.retrieval import search_knowledge
from api.app.settings import Settings, get_settings
from api.app.slack.attachments import evidence_to_chunks
from mcp_server.tools.onboarding import ONBOARDING_NOT_CONFIGURED_MESSAGE

logger = get_logger("api.agent.nodes.tools")

# Workflows that use an MCP meeting-draft tool (citations + markdown outline)
_MEETING_DRAFT_TOOLS = frozenset(
    {"meeting_brief", "meeting_agenda", "meeting_notes"}
)

# File / workflow-advice still optionally RAG, but attachments count as evidence
_FILE_WORKFLOWS = frozenset(
    {"file_analyse", "file_pdf_export", "file_rename", "workflow_advise"}
)

_MEETING_DRAFT_FN = {
    "meeting_brief": draft_meeting_brief_via_mcp,
    "meeting_agenda": draft_meeting_agenda_via_mcp,
    "meeting_notes": draft_meeting_notes_via_mcp,
}


def make_tools_node(
    *,
    settings: Settings | None = None,
    search_fn: Optional[SearchFn] = None,
    mcp_call_tool: Optional[McpCallTool] = None,
    top_k: int | None = None,
) -> Callable[[AgentState], dict[str, Any]]:
    """
    Build the agent tool node.

    Default: call MCP ``search_knowledge`` over stdio (not an in-process
    duplicate of retrieval). For meeting brief / agenda / notes, call the
    matching MCP draft tool. For ``report``, call MCP ``draft_report``.
    For ``onboarding``, call MCP ``start_onboarding`` (stub). Inject
    ``search_fn`` to skip MCP (unit tests), or ``mcp_call_tool`` to
    stub the MCP transport.
    """
    settings = settings or get_settings()
    limit = top_k if top_k is not None else settings.agent_retrieve_top_k
    backend = (settings.agent_retrieve_backend or "mcp").strip().lower()

    if search_fn is not None:
        search: SearchFn | None = search_fn
        via = "inject"
    elif backend == "direct":
        search = search_knowledge
        via = "direct"
    else:
        search = None
        via = "mcp"

    def tools_node(state: AgentState) -> dict[str, Any]:
        client_id = require_tenant_client_id(
            state.get("client_id"),
            where="tools",
        )

        question = (state.get("question") or "").strip()
        workflow = state.get("workflow") or "qa"
        if not question:
            logger.info(
                "agent_tools skip empty question client_id=%s via=%s",
                client_id,
                via,
            )
            return {
                "client_id": client_id,
                "retrieved_chunks": [],
                "hedge": True,
                "meeting_draft": "",
            }

        min_score = float(settings.agent_min_score)

        # Onboarding stub — no RAG; clear “not configured” message
        if workflow == "onboarding":
            if search is None:
                payload = start_onboarding_via_mcp(
                    client_id=client_id,
                    settings=settings,
                    call_tool=mcp_call_tool,
                )
                message = str(
                    payload.get("message")
                    or payload.get("markdown")
                    or ONBOARDING_NOT_CONFIGURED_MESSAGE
                ).strip()
            else:
                message = ONBOARDING_NOT_CONFIGURED_MESSAGE
            logger.info(
                "agent_tools client_id=%s via=%s workflow=%s configured=false",
                client_id,
                via,
                workflow,
            )
            return {
                "client_id": client_id,
                "retrieved_chunks": [],
                "hedge": False,
                "meeting_draft": message,
            }

        # Recurring report: MCP draft_report → outline + hits
        if workflow == "report" and search is None:
            window = (state.get("report_window") or "").strip() or question
            channel = (state.get("report_channel") or "").strip() or None
            draft = draft_report_via_mcp(
                client_id=client_id,
                window_label=window,
                topic=question,
                channel=channel,
                limit=limit,
                settings=settings,
                call_tool=mcp_call_tool,
            )
            hits_raw = draft.get("citations") or []
            raw = [
                citation_to_chunk(citation_from_mcp_hit(h))
                for h in hits_raw
                if isinstance(h, dict)
            ]
            chunks = filter_chunks_for_tenant(raw, client_id, min_score=min_score)
            hedge = bool(draft.get("hedged")) or should_hedge(chunks)
            markdown = str(draft.get("markdown") or "").strip()
            logger.info(
                "agent_tools client_id=%s via=%s workflow=%s hits=%s hedge=%s",
                client_id,
                via,
                workflow,
                len(chunks),
                hedge,
            )
            return {
                "client_id": client_id,
                "retrieved_chunks": chunks,
                "hedge": hedge,
                "meeting_draft": markdown if not hedge else "",
                "report_window": window,
            }

        # Meeting brief / agenda / notes: MCP draft helper → outline + hits
        if workflow in _MEETING_DRAFT_TOOLS and search is None:
            draft_fn = _MEETING_DRAFT_FN[workflow]
            draft = draft_fn(
                client_id=client_id,
                topic=question,
                limit=limit,
                settings=settings,
                call_tool=mcp_call_tool,
            )
            hits_raw = draft.get("citations") or []
            raw = [
                citation_to_chunk(citation_from_mcp_hit(h))
                for h in hits_raw
                if isinstance(h, dict)
            ]
            chunks = filter_chunks_for_tenant(raw, client_id, min_score=min_score)
            hedge = bool(draft.get("hedged")) or should_hedge(chunks)
            markdown = str(draft.get("markdown") or "").strip()
            logger.info(
                "agent_tools client_id=%s via=%s workflow=%s hits=%s hedge=%s",
                client_id,
                via,
                workflow,
                len(chunks),
                hedge,
            )
            return {
                "client_id": client_id,
                "retrieved_chunks": chunks,
                "hedge": hedge,
                "meeting_draft": markdown if not hedge else "",
            }

        # Default RAG path (inject / direct / mcp search)
        if search is not None:
            result = search(
                client_id=client_id,
                query=question,
                limit=limit,
                score_threshold=min_score,
                settings=settings,
            )
        else:
            result = search_knowledge_via_mcp(
                client_id=client_id,
                query=question,
                limit=limit,
                score_threshold=min_score,
                settings=settings,
                call_tool=mcp_call_tool,
            )

        raw = [citation_to_chunk(h) for h in result.hits]
        rag_chunks = filter_chunks_for_tenant(raw, client_id, min_score=min_score)

        attach_chunks = evidence_to_chunks(
            list(state.get("attached_evidence") or []),
            client_id=client_id,
        )
        # Attachments first so compose evidence leads with the file
        chunks = attach_chunks + rag_chunks
        hedge = should_hedge(chunks)
        if workflow in _FILE_WORKFLOWS and not attach_chunks:
            # File workflow without usable attachment text → hedge with clear gap
            hedge = True
        logger.info(
            "agent_tools client_id=%s via=%s workflow=%s hits=%s attachments=%s hedge=%s",
            client_id,
            via,
            workflow,
            len(rag_chunks),
            len(attach_chunks),
            hedge,
        )
        return {
            "client_id": client_id,
            "retrieved_chunks": chunks,
            "hedge": hedge,
            "meeting_draft": "",
            "attached_evidence": list(state.get("attached_evidence") or []),
        }

    return tools_node
