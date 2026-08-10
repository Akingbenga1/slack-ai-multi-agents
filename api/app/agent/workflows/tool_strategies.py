"""ToolStrategy map — workflow → tools-node algorithm (Sprint 25.4).

Each workflow picks a Strategy that gathers evidence / drafts for compose.
``make_tools_node`` stays thin: resolve search backend, then
``get_tool_strategy(workflow).run(state, ctx)``.

How to add a tools path:
1. Implement ``ToolStrategy.run`` (or reuse ``RagToolStrategy`` / meeting factory).
2. Register it in ``TOOL_STRATEGIES`` (and default via ``get_tool_strategy``).
3. Keep classifier + ``WorkflowMeta`` in sync (see ``registry.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

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
from api.app.agent.state import AgentState, WorkflowName
from api.app.logging_config import get_logger
from api.app.settings import Settings
from api.app.slack.attachments import evidence_to_chunks
from mcp_server.tools.onboarding import ONBOARDING_NOT_CONFIGURED_MESSAGE

logger = get_logger("api.agent.workflows.tool_strategies")

# File / workflow-advice still optionally RAG, but attachments count as evidence
_ATTACHMENT_PRIMARY = frozenset(
    {"file_analyse", "file_pdf_export", "file_rename", "workflow_advise"}
)

MeetingDraftFn = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ToolsContext:
    """Resolved injectables for one tools-node invoke (search backend + MCP)."""

    settings: Settings
    search: SearchFn | None
    mcp_call_tool: Optional[McpCallTool]
    limit: int
    via: str  # inject | direct | mcp


class ToolStrategy(Protocol):
    """Strategy contract: gather chunks / draft markdown for one workflow."""

    def run(self, state: AgentState, ctx: ToolsContext) -> dict[str, Any]:
        """Return state patch (retrieved_chunks, hedge, meeting_draft, …)."""


def empty_question_result(client_id: str) -> dict[str, Any]:
    return {
        "client_id": client_id,
        "retrieved_chunks": [],
        "hedge": True,
        "meeting_draft": "",
    }


class OnboardingToolStrategy:
    """MCP ``start_onboarding`` stub (or fixed message when search is injected)."""

    def run(self, state: AgentState, ctx: ToolsContext) -> dict[str, Any]:
        client_id = require_tenant_client_id(state.get("client_id"), where="tools")
        if ctx.search is None:
            payload = start_onboarding_via_mcp(
                client_id=client_id,
                settings=ctx.settings,
                call_tool=ctx.mcp_call_tool,
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
            ctx.via,
            "onboarding",
        )
        return {
            "client_id": client_id,
            "retrieved_chunks": [],
            "hedge": False,
            "meeting_draft": message,
        }


class RagToolStrategy:
    """Default grounded path: inject / direct / MCP search + optional attachments."""

    def __init__(self, *, hedge_without_attachments: bool = False) -> None:
        self._hedge_without_attachments = hedge_without_attachments

    def run(self, state: AgentState, ctx: ToolsContext) -> dict[str, Any]:
        client_id = require_tenant_client_id(state.get("client_id"), where="tools")
        question = (state.get("question") or "").strip()
        workflow = state.get("workflow") or "qa"
        min_score = float(ctx.settings.agent_min_score)

        if ctx.search is not None:
            result = ctx.search(
                client_id=client_id,
                query=question,
                limit=ctx.limit,
                score_threshold=min_score,
                settings=ctx.settings,
            )
        else:
            result = search_knowledge_via_mcp(
                client_id=client_id,
                query=question,
                limit=ctx.limit,
                score_threshold=min_score,
                settings=ctx.settings,
                call_tool=ctx.mcp_call_tool,
            )

        raw = [citation_to_chunk(h) for h in result.hits]
        rag_chunks = filter_chunks_for_tenant(raw, client_id, min_score=min_score)

        attach_chunks = evidence_to_chunks(
            list(state.get("attached_evidence") or []),
            client_id=client_id,
        )
        chunks = attach_chunks + rag_chunks
        hedge = should_hedge(chunks)
        force_attach_hedge = (
            self._hedge_without_attachments or workflow in _ATTACHMENT_PRIMARY
        )
        if force_attach_hedge and not attach_chunks:
            hedge = True
        logger.info(
            "agent_tools client_id=%s via=%s workflow=%s hits=%s attachments=%s hedge=%s",
            client_id,
            ctx.via,
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


class ReportToolStrategy:
    """MCP ``draft_report`` when using MCP; else fall through to RAG (tests)."""

    def __init__(self, rag: RagToolStrategy) -> None:
        self._rag = rag

    def run(self, state: AgentState, ctx: ToolsContext) -> dict[str, Any]:
        if ctx.search is not None:
            return self._rag.run(state, ctx)

        client_id = require_tenant_client_id(state.get("client_id"), where="tools")
        question = (state.get("question") or "").strip()
        window = (state.get("report_window") or "").strip() or question
        channel = (state.get("report_channel") or "").strip() or None
        min_score = float(ctx.settings.agent_min_score)
        draft = draft_report_via_mcp(
            client_id=client_id,
            window_label=window,
            topic=question,
            channel=channel,
            limit=ctx.limit,
            settings=ctx.settings,
            call_tool=ctx.mcp_call_tool,
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
            ctx.via,
            "report",
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


class MeetingDraftToolStrategy:
    """MCP meeting draft helper; RAG fallthrough when ``search`` is injected."""

    def __init__(
        self,
        workflow: WorkflowName,
        draft_fn: MeetingDraftFn,
        rag: RagToolStrategy,
    ) -> None:
        self._workflow = workflow
        self._draft_fn = draft_fn
        self._rag = rag

    def run(self, state: AgentState, ctx: ToolsContext) -> dict[str, Any]:
        if ctx.search is not None:
            return self._rag.run(state, ctx)

        client_id = require_tenant_client_id(state.get("client_id"), where="tools")
        question = (state.get("question") or "").strip()
        min_score = float(ctx.settings.agent_min_score)
        draft = self._draft_fn(
            client_id=client_id,
            topic=question,
            limit=ctx.limit,
            settings=ctx.settings,
            call_tool=ctx.mcp_call_tool,
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
            ctx.via,
            self._workflow,
            len(chunks),
            hedge,
        )
        return {
            "client_id": client_id,
            "retrieved_chunks": chunks,
            "hedge": hedge,
            "meeting_draft": markdown if not hedge else "",
        }


class DirectRetrieveStrategy:
    """In-process RAG only — tests / ``AGENT_RETRIEVE_BACKEND=direct`` quarantine.

    Not used by the production tools → MCP path. ``make_retrieve_node`` wraps
    this Strategy for debug graphs that still want a standalone retrieve node.
    """

    def run(
        self,
        state: AgentState,
        *,
        settings: Settings,
        search: SearchFn,
        limit: int,
    ) -> dict[str, Any]:
        client_id = require_tenant_client_id(
            state.get("client_id"),
            where="retrieve",
        )
        question = (state.get("question") or "").strip()
        if not question:
            logger.info("agent_retrieve skip empty question client_id=%s", client_id)
            return {
                "client_id": client_id,
                "retrieved_chunks": [],
                "hedge": True,
            }

        min_score = float(settings.agent_min_score)
        result = search(
            client_id=client_id,
            query=question,
            limit=limit,
            score_threshold=min_score,
            settings=settings,
        )
        raw = [citation_to_chunk(h) for h in result.hits]
        chunks = filter_chunks_for_tenant(raw, client_id, min_score=min_score)
        hedge = should_hedge(chunks)
        logger.info(
            "agent_retrieve client_id=%s hits=%s hedge=%s",
            client_id,
            len(chunks),
            hedge,
        )
        return {
            "client_id": client_id,
            "retrieved_chunks": chunks,
            "hedge": hedge,
        }


_RAG = RagToolStrategy()
_RAG_ATTACH = RagToolStrategy(hedge_without_attachments=True)

TOOL_STRATEGIES: dict[str, ToolStrategy] = {
    "onboarding": OnboardingToolStrategy(),
    "report": ReportToolStrategy(_RAG),
    "meeting_brief": MeetingDraftToolStrategy(
        "meeting_brief", draft_meeting_brief_via_mcp, _RAG
    ),
    "meeting_agenda": MeetingDraftToolStrategy(
        "meeting_agenda", draft_meeting_agenda_via_mcp, _RAG
    ),
    "meeting_notes": MeetingDraftToolStrategy(
        "meeting_notes", draft_meeting_notes_via_mcp, _RAG
    ),
    "file_analyse": _RAG_ATTACH,
    "file_pdf_export": _RAG_ATTACH,
    "file_rename": _RAG_ATTACH,
    "workflow_advise": _RAG_ATTACH,
    # Default RAG for qa / summarize / status / library / unknown
    "qa": _RAG,
    "summarize": _RAG,
    "status": _RAG,
    "workflow_store": _RAG,
    "workflow_list": _RAG,
    "workflow_copy": _RAG,
    "workflow_edit": _RAG,
    "unknown": _RAG,
}

DIRECT_RETRIEVE = DirectRetrieveStrategy()


def get_tool_strategy(workflow: WorkflowName | str | None) -> ToolStrategy:
    """Return the ToolStrategy for a workflow; defaults to RAG."""
    key = (workflow or "qa")
    if isinstance(key, str):
        key = key.strip() or "qa"
    return TOOL_STRATEGIES.get(key, _RAG)


def resolve_tools_context(
    *,
    settings: Settings,
    search_fn: Optional[SearchFn] = None,
    mcp_call_tool: Optional[McpCallTool] = None,
    top_k: int | None = None,
    direct_search: SearchFn | None = None,
) -> ToolsContext:
    """Resolve inject / direct / mcp search backend for the tools node."""
    from api.app.retrieval import search_knowledge

    limit = top_k if top_k is not None else settings.agent_retrieve_top_k
    backend = (settings.agent_retrieve_backend or "mcp").strip().lower()
    direct = direct_search or search_knowledge

    if search_fn is not None:
        return ToolsContext(
            settings=settings,
            search=search_fn,
            mcp_call_tool=mcp_call_tool,
            limit=limit,
            via="inject",
        )
    if backend == "direct":
        return ToolsContext(
            settings=settings,
            search=direct,
            mcp_call_tool=mcp_call_tool,
            limit=limit,
            via="direct",
        )
    return ToolsContext(
        settings=settings,
        search=None,
        mcp_call_tool=mcp_call_tool,
        limit=limit,
        via="mcp",
    )


__all__ = [
    "DIRECT_RETRIEVE",
    "TOOL_STRATEGIES",
    "DirectRetrieveStrategy",
    "MeetingDraftToolStrategy",
    "OnboardingToolStrategy",
    "RagToolStrategy",
    "ReportToolStrategy",
    "ToolStrategy",
    "ToolsContext",
    "empty_question_result",
    "get_tool_strategy",
    "resolve_tools_context",
]
