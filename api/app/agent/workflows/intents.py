"""Shared intent helpers for Slack delivery actions.

These helpers detect secondary intents (rename, PDF, advise) in question text
for post-processing delivery. They are NOT used for pre-classification —
the orchestrator LLM decides the workflow type.
"""

from __future__ import annotations

import re

WORKFLOW_ADVISE_RE = re.compile(
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

FILE_RENAME_BROAD_RE = re.compile(
    r"("
    r"\brename\b|"
    r"\b(change|update)\s+(the\s+)?(file\s+)?name\b|"
    r"\bfile_rename\b"
    r")",
    re.I,
)

FILE_PDF_EXPORT_RE = re.compile(
    r"("
    r"\b(produce|generate|create|export|make|draft)\s+(a\s+|an\s+|the\s+)?pdf\b|"
    r"\bpdf\s+(of|for|deliverable|export|report)\b|"
    r"\bcompetitor\s+analysis\b|"
    r"\b(downloadable|shareable)\s+pdf\b|"
    r"\bfile_pdf_export\b"
    r")",
    re.I,
)


def question_requests_workflow_advice(question: str) -> bool:
    """True when the ask also wants file-grounded operationalisation advice."""
    return bool(WORKFLOW_ADVISE_RE.search((question or "").strip()))


def question_requests_rename(question: str) -> bool:
    """True when the ask includes a file-rename intent (combined asks)."""
    return bool(FILE_RENAME_BROAD_RE.search(question or ""))


def question_requests_pdf_export(question: str) -> bool:
    """True when the ask includes a PDF-export intent."""
    return bool(FILE_PDF_EXPORT_RE.search(question or ""))
