"""Workflow metadata registry (Sprint 25.2).

How to add a workflow (pointer for Sprint 30 docs):
1. Add the name to ``WorkflowName`` in ``api/app/agent/state.py``.
2. Register ``WorkflowMeta`` here (prompts / delivery_hint / escalate).
3. Add a classifier rule in ``workflows/rules.py`` (ordered).
4. Register a ``ToolStrategy`` in ``workflows/tool_strategies.py`` (or reuse RAG /
   meeting / report strategies) + compose prompt in ``prompts.py``.
5. Register a DeliveryStrategy under ``api.app.slack.delivery`` when side
   effects differ (Sprint 26).

Do **not** extend the old monolithic regex/`if` ladders in ``route`` / ``tools``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal

from api.app.agent.state import WorkflowName

DeliveryHint = Literal[
    "default",
    "pdf_upload",
    "rename",
    "library_confirm",
    "none",
]


@dataclass(frozen=True)
class WorkflowMeta:
    """Static metadata for one registered workflow capability."""

    name: WorkflowName
    description: str
    prompt_key: WorkflowName
    escalate: bool = False
    delivery_hint: DeliveryHint = "default"


# Ordered for docs / parametrized tests — classification order lives in rules.py.
_WORKFLOW_METAS: tuple[WorkflowMeta, ...] = (
    WorkflowMeta(
        name="qa",
        description="Default grounded Q&A over tenant knowledge",
        prompt_key="qa",
    ),
    WorkflowMeta(
        name="summarize",
        description="Thread / channel summary (coordination)",
        prompt_key="summarize",
        escalate=True,
    ),
    WorkflowMeta(
        name="status",
        description="Status / attribution questions (coordination)",
        prompt_key="status",
        escalate=True,
    ),
    WorkflowMeta(
        name="meeting_brief",
        description="Pre-meeting brief draft via MCP",
        prompt_key="meeting_brief",
        escalate=True,
    ),
    WorkflowMeta(
        name="meeting_agenda",
        description="Meeting agenda draft via MCP",
        prompt_key="meeting_agenda",
        escalate=True,
    ),
    WorkflowMeta(
        name="meeting_notes",
        description="Meeting notes draft via MCP",
        prompt_key="meeting_notes",
        escalate=True,
    ),
    WorkflowMeta(
        name="report",
        description="Recurring team digest / report",
        prompt_key="report",
        escalate=True,
    ),
    WorkflowMeta(
        name="onboarding",
        description="Client onboarding stub (not configured)",
        prompt_key="onboarding",
        delivery_hint="none",
    ),
    WorkflowMeta(
        name="file_analyse",
        description="Analyse Slack attachment(s)",
        prompt_key="file_analyse",
        escalate=True,
    ),
    WorkflowMeta(
        name="file_pdf_export",
        description="Analyse attachment and deliver PDF",
        prompt_key="file_pdf_export",
        escalate=True,
        delivery_hint="pdf_upload",
    ),
    WorkflowMeta(
        name="file_rename",
        description="Rename Slack attachment / stored copy",
        prompt_key="file_rename",
        delivery_hint="rename",
    ),
    WorkflowMeta(
        name="workflow_store",
        description="Store uploaded workflow in shared library",
        prompt_key="workflow_store",
        delivery_hint="library_confirm",
    ),
    WorkflowMeta(
        name="workflow_list",
        description="List shared workflow library entries",
        prompt_key="workflow_list",
        delivery_hint="library_confirm",
    ),
    WorkflowMeta(
        name="workflow_copy",
        description="Copy shared workflow to personal draft",
        prompt_key="workflow_copy",
        delivery_hint="library_confirm",
    ),
    WorkflowMeta(
        name="workflow_edit",
        description="Edit personal workflow draft",
        prompt_key="workflow_edit",
        delivery_hint="library_confirm",
    ),
    WorkflowMeta(
        name="workflow_advise",
        description="File-grounded operationalisation advice",
        prompt_key="workflow_advise",
        escalate=True,
    ),
    WorkflowMeta(
        name="unknown",
        description="Empty / unclassifiable question",
        prompt_key="qa",
        delivery_hint="none",
    ),
)

WORKFLOW_REGISTRY: dict[WorkflowName, WorkflowMeta] = {
    meta.name: meta for meta in _WORKFLOW_METAS
}


def get_workflow_meta(name: WorkflowName | str) -> WorkflowMeta:
    """Return metadata for a workflow name; falls back to ``qa``."""
    key = (name or "qa").strip()  # type: ignore[union-attr]
    return WORKFLOW_REGISTRY.get(key, WORKFLOW_REGISTRY["qa"])  # type: ignore[arg-type]


def list_workflow_names() -> tuple[WorkflowName, ...]:
    """All registered workflow names (registry order)."""
    return tuple(meta.name for meta in _WORKFLOW_METAS)


def iter_workflow_meta() -> Iterator[WorkflowMeta]:
    """Iterate registered workflow metadata in registry order."""
    yield from _WORKFLOW_METAS
