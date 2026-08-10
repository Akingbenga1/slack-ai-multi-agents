"""Route node — classify workflow + seed model tier."""

from __future__ import annotations

import re
from typing import Any

from api.app.agent.guardrails import require_tenant_client_id
from api.app.agent.llm import message_content
from api.app.agent.policy import choose_model_tier, detect_complexity_flags
from api.app.agent.state import AgentState, WorkflowName
from api.app.logging_config import get_logger

logger = get_logger("api.agent.nodes.route")

# Meeting workflows (Sprint 16.1) — checked before generic coordination / qa.
# Avoid bare "brief" (false positives on "brief overview"); require meeting cues.
_MEETING_BRIEF = re.compile(
    r"("
    r"\bmeeting\s+brief\b|"
    r"\bpre[- ]?meeting(\s+brief)?\b|"
    r"\bbrief\s+me\b|"
    r"\bbrief\s+(me\s+)?(for|on)\b|"
    r"\bprep\s+me\s+(for|on)\b|"
    r"\bprepare\s+me\s+(for|on)\b|"
    r"\b(pre[- ]?)?meeting\s+prep\b|"
    r"\bbriefing\s+(for|on)\b|"
    r"\b(draft|write|prepare)\s+(a\s+)?(pre[- ]?meeting\s+)?brief\b"
    r")",
    re.I,
)
_MEETING_AGENDA = re.compile(
    r"("
    r"\b(meeting\s+)?agenda\b|"
    r"\bdraft\s+(an\s+)?agenda\b|"
    r"\bagenda\s+for\b|"
    r"\b(build|create|write|make)\s+(an?\s+)?agenda\b"
    r")",
    re.I,
)
_MEETING_NOTES = re.compile(
    r"("
    r"\bmeeting\s+notes\b|"
    r"\bnotes\s+(from|for)\s+(the\s+)?(meeting|call|discussion|sync)\b|"
    r"\b(take|draft|capture|write)\s+(meeting\s+)?notes\b|"
    r"\bnotes\s+from\s+recent\b"
    r")",
    re.I,
)

# Onboarding process stub (Sprint 18.1) — explicit start/process phrasing only.
# Bare "onboarding checklist…" stays qa (knowledge search).
_ONBOARDING = re.compile(
    r"("
    r"\b(start|begin|kick\s*off|run|launch)\s+(the\s+)?(client\s+)?onboarding\b|"
    r"\bonboarding\s+(process|workflow)\b|"
    r"\b(start|begin)\s+(the\s+)?onboarding\s+(process|workflow|checklist)\b|"
    r"\bstart_onboarding\b"
    r")",
    re.I,
)

# Slack file actions (Sprint 23) — before meeting / report / generic qa.
# Shared workflow library (Sprint 24) — before generic file analyse.
_WORKFLOW_STORE = re.compile(
    r"("
    r"\b(store|save|add)\s+(this|the|my)?\s*(attached\s+)?(workflow|template|process)\b|"
    r"\b(store|save)\s+(this|the|my)?\s*(attached\s+)?(workflow\s+)?"
    r"(description|file|attachment|document)\b|"
    r"\b(store|save)\s+(it|this|that)\s+(in|to|for)\s+(the\s+)?(shared\s+)?"
    r"(library|colleagues|team)\b|"
    r"\bshared\s+(workflow\s+)?library\b|"
    r"\bstore\s+(this|the)\s+(file|attachment|document)\s+(for\s+)?colleagues\b|"
    r"\bworkflow_store\b"
    r")",
    re.I,
)
_WORKFLOW_COPY = re.compile(
    r"("
    r"\b(copy|duplicate)\s+(this|the|my|a|an)?\s*(workflow|template)\b|"
    r"\b(make|create)\s+(a\s+)?(personal\s+)?(copy|draft)\b|"
    r"\bworkflow_copy\b"
    r")",
    re.I,
)
_WORKFLOW_EDIT = re.compile(
    r"("
    r"\b(edit|update|modify|rename|retitle)\s+(my\s+)?(workflow\s+)?"
    r"(draft|copy|personal\s+template)\b|"
    r"\b(set|change)\s+(the\s+)?(title|body|text|content)\s+(of\s+)?"
    r"(my\s+)?(draft|copy)\b|"
    r"\bworkflow_edit\b"
    r")",
    re.I,
)
_WORKFLOW_LIST = re.compile(
    r"("
    r"\b(list|show|find|search|browse)\s+(shared\s+)?(workflow|template)s?\b|"
    r"\b(what|which)\s+workflows?\s+(do\s+we\s+have|are\s+stored|in\s+the\s+library)\b|"
    r"\bworkflow_list\b"
    r")",
    re.I,
)
_WORKFLOW_ADVISE = re.compile(
    r"("
    r"\b(advise|advice)\s+(on|about|for|how)\s+"
    r"(this|the|our|my|a|an)?\s*(attached\s+)?"
    r"(workflow|template|process|file|attachment)\b|"
    r"\badvise\s+(me\s+)?how\s+(to|we|i)\b.*\b(workflow|template|process)\b|"
    r"\bhow\s+(can|do|should)\s+(we|i|our\s+team)\s+"
    r"(make|operationali[sz]e|implement|run|use|adopt)\s+"
    r"(this|the|our|my)?\s*(workflow|template|process)\b|"
    r"\bhow\s+to\s+(make|operationali[sz]e|implement|run|use)\s+"
    r"(this|the|our|my)?\s*(workflow|template|process)\b|"
    r"\boperationali[sz]e\s+(this|the|our|my)?\s*(workflow|template)\b|"
    r"\bmake\s+(this|the)\s+workflow\s+work\b|"
    r"\bworkflow_advise\b|"
    r"\badvise_workflow\b"
    r")",
    re.I | re.S,
)
_FILE_RENAME = re.compile(
    r"("
    r"\brename\s+(the\s+)?(file|attachment|document|report)\b|"
    r"\brename\s+(this|that|it)\b|"
    r"\b(change|update)\s+(the\s+)?(file\s+)?name\b|"
    r"\bfile_rename\b"
    r")",
    re.I,
)
_FILE_PDF_EXPORT = re.compile(
    r"("
    r"\b(produce|generate|create|export|make|draft)\s+(a\s+|an\s+|the\s+)?pdf\b|"
    r"\bpdf\s+(of|for|deliverable|export|report)\b|"
    r"\bcompetitor\s+analysis\b|"
    r"\b(downloadable|shareable)\s+pdf\b|"
    r"\bfile_pdf_export\b"
    r")",
    re.I,
)
_FILE_ANALYSE = re.compile(
    r"("
    r"\b(analy[sz]e|analysis|review|summarize|summarise)\s+"
    r"(this|the|my|attached|from)\b|"
    r"\b(from|based\s+on|using)\s+(this|the|my|attached)\s+"
    r"(file|attachment|document|report|pdf)\b|"
    r"\b(attached|attachment)\s+(file|document|report)?\b|"
    r"\bfile_analyse\b|"
    r"\bread\s+(this|the)\s+(file|attachment|document)\b"
    r")",
    re.I,
)

# Recurring report / digest (Sprint 17.1) — before generic summarize (which
# also matches bare "digest").
_REPORT = re.compile(
    r"("
    r"\b(recurring|weekly|daily|monthly|team|status)\s+report\b|"
    r"\breport\s+(for|on|over)\b|"
    r"\b(generate|draft|write|post|produce)\s+(a\s+|the\s+)?(weekly\s+|daily\s+|monthly\s+|team\s+)?(report|digest)\b|"
    r"\b(weekly|daily|monthly)\s+digest\b|"
    r"\bchannel\s+digest\b|"
    r"\bdigest\s+(for|of)\s+(the\s+)?(week|channel|team)\b"
    r")",
    re.I,
)

# Coordination-style intents (Sprint 14.4) — still RAG-grounded via retrieve.
_SUMMARIZE = re.compile(
    r"\b("
    r"summariz\w*|summary|recap|tl;?dr|catch me up|what did i miss|"
    r"sum up|rundown|digest"
    r")\b",
    re.I,
)
_STATUS = re.compile(
    r"\b("
    r"status|who said|who mentioned|who.?s working|who is working|"
    r"what.?s the latest|any update|where are we|progress on|"
    r"who.?s on|owners? of"
    r")\b",
    re.I,
)


def classify_workflow(
    question: str,
    *,
    has_attachments: bool = False,
) -> WorkflowName:
    """Classify file / meeting / onboarding / report / coordination / qa workflows."""
    text = (question or "").strip()
    if not text:
        return "unknown"
    # File-transform intents (Sprint 23) — before meeting/report generics.
    # Shared workflow library (Sprint 24) before generic file analyse.
    if _WORKFLOW_STORE.search(text):
        return "workflow_store"
    if _WORKFLOW_COPY.search(text):
        return "workflow_copy"
    if _WORKFLOW_EDIT.search(text):
        return "workflow_edit"
    if _WORKFLOW_LIST.search(text):
        return "workflow_list"
    if _WORKFLOW_ADVISE.search(text):
        return "workflow_advise"
    # Prefer PDF export when both analyse + PDF are requested (J10 journey).
    if _FILE_PDF_EXPORT.search(text):
        return "file_pdf_export"
    if _FILE_RENAME.search(text) and not _FILE_ANALYSE.search(text):
        return "file_rename"
    if _FILE_RENAME.search(text) and _FILE_PDF_EXPORT.search(text):
        return "file_pdf_export"
    if _FILE_ANALYSE.search(text):
        return "file_analyse"
    if has_attachments and re.search(
        r"\b(this|attached|attachment|file|document|report)\b",
        text,
        re.I,
    ):
        return "file_analyse"
    # Meeting intents first (more specific than summarize/status).
    if _MEETING_AGENDA.search(text):
        return "meeting_agenda"
    if _MEETING_NOTES.search(text):
        return "meeting_notes"
    if _MEETING_BRIEF.search(text):
        return "meeting_brief"
    # Explicit onboarding process start (before generic qa about onboarding).
    if _ONBOARDING.search(text):
        return "onboarding"
    # Recurring report before bare "digest" → summarize.
    if _REPORT.search(text):
        return "report"
    if _SUMMARIZE.search(text):
        return "summarize"
    if _STATUS.search(text):
        return "status"
    return "qa"


def question_requests_workflow_advice(question: str) -> bool:
    """True when the ask also wants file-grounded operationalisation advice."""
    return bool(_WORKFLOW_ADVISE.search((question or "").strip()))


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
