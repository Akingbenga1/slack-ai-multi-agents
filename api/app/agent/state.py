"""LangGraph agent state (Sprint 13)."""

from __future__ import annotations

from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langgraph.graph.message import add_messages

# Vendor-neutral tiers — adapters map to concrete model ids (Sprint 33)
ModelTier = Literal["fast", "capable"]
WorkflowName = Literal[
    "qa",
    "summarize",
    "status",
    "meeting_brief",
    "meeting_agenda",
    "meeting_notes",
    "report",
    "onboarding",
    "file_analyse",
    "file_pdf_export",
    "file_rename",
    "workflow_store",
    "workflow_list",
    "workflow_copy",
    "workflow_edit",
    "workflow_advise",
    "unknown",
]

# Heavy Slack file jobs — budget-gated before graph (Sprint 23.2 / 24.2)
FILE_HEAVY_WORKFLOWS: frozenset[WorkflowName] = frozenset(
    {"file_pdf_export", "file_rename", "workflow_store"}
)


class AgentState(TypedDict):
    """Shared graph state — tenant isolation fields must never be dropped."""

    client_id: str
    messages: Annotated[list, add_messages]
    retrieved_chunks: list[dict[str, Any]]
    workflow: WorkflowName
    model_tier: ModelTier
    complexity_flags: NotRequired[list[str]]
    # Last user question text (convenience for retrieve/compose)
    question: NotRequired[str]
    # Compose output (also mirrored into messages as AI)
    answer: NotRequired[str]
    # Token usage from last compose call
    usage_tokens: NotRequired[int]
    # Hedge when no tenant-scoped retrieval evidence (hard message in compose)
    hedge: NotRequired[bool]
    # MCP draft outline markdown (meeting / report) for compose polish
    meeting_draft: NotRequired[str]
    # Recurring report window label (e.g. "last 7 days")
    report_window: NotRequired[str]
    # Optional Slack channel id for channel-scoped report retrieval
    report_channel: NotRequired[str]
    # Optional org-level system prompt overlay from agent_configs
    org_system_prompt: NotRequired[str]
    # Slack attachment evidence (Sprint 23) — not only Qdrant RAG
    attached_evidence: NotRequired[list[dict[str, Any]]]
    # PDF / rename deliverable metadata from post-compose file actions
    file_action_result: NotRequired[dict[str, Any]]
