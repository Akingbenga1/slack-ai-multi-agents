"""Shared Slack / route intent patterns (Sprint 25.3).

Single source for file rename / PDF / workflow-advise cues so ``route``
classification and Slack helpers do not redefine the same regexes.
"""

from __future__ import annotations

import re

# --- Shared workflow library (Sprint 24) ---

WORKFLOW_STORE_RE = re.compile(
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

WORKFLOW_COPY_RE = re.compile(
    r"("
    r"\b(copy|duplicate)\s+(this|the|my|a|an)?\s*(workflow|template)\b|"
    r"\b(make|create)\s+(a\s+)?(personal\s+)?(copy|draft)\b|"
    r"\bworkflow_copy\b"
    r")",
    re.I,
)

WORKFLOW_EDIT_RE = re.compile(
    r"("
    r"\b(edit|update|modify|rename|retitle)\s+(my\s+)?(workflow\s+)?"
    r"(draft|copy|personal\s+template)\b|"
    r"\b(set|change)\s+(the\s+)?(title|body|text|content)\s+(of\s+)?"
    r"(my\s+)?(draft|copy)\b|"
    r"\bworkflow_edit\b"
    r")",
    re.I,
)

WORKFLOW_LIST_RE = re.compile(
    r"("
    r"\b(list|show|find|search|browse)\s+(shared\s+)?(workflow|template)s?\b|"
    r"\b(what|which)\s+workflows?\s+(do\s+we\s+have|are\s+stored|in\s+the\s+library)\b|"
    r"\bworkflow_list\b"
    r")",
    re.I,
)

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

# --- Slack file actions (Sprint 23) ---

# Classifier: specific rename phrasing (avoids false positives on unrelated text).
FILE_RENAME_RE = re.compile(
    r"("
    r"\brename\s+(the\s+)?(file|attachment|document|report)\b|"
    r"\brename\s+(this|that|it)\b|"
    r"\b(change|update)\s+(the\s+)?(file\s+)?name\b|"
    r"\bfile_rename\b"
    r")",
    re.I,
)

# Slack combined-ask helper: broader cue (any "rename") after PDF path.
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

FILE_ANALYSE_RE = re.compile(
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

ATTACHMENT_CUE_RE = re.compile(
    r"\b(this|attached|attachment|file|document|report)\b",
    re.I,
)

# --- Meeting (Sprint 16) ---

MEETING_BRIEF_RE = re.compile(
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

MEETING_AGENDA_RE = re.compile(
    r"("
    r"\b(meeting\s+)?agenda\b|"
    r"\bdraft\s+(an\s+)?agenda\b|"
    r"\bagenda\s+for\b|"
    r"\b(build|create|write|make)\s+(an?\s+)?agenda\b"
    r")",
    re.I,
)

MEETING_NOTES_RE = re.compile(
    r"("
    r"\bmeeting\s+notes\b|"
    r"\bnotes\s+(from|for)\s+(the\s+)?(meeting|call|discussion|sync)\b|"
    r"\b(take|draft|capture|write)\s+(meeting\s+)?notes\b|"
    r"\bnotes\s+from\s+recent\b"
    r")",
    re.I,
)

# --- Onboarding / report / coordination ---

ONBOARDING_RE = re.compile(
    r"("
    r"\b(start|begin|kick\s*off|run|launch)\s+(the\s+)?(client\s+)?onboarding\b|"
    r"\bonboarding\s+(process|workflow)\b|"
    r"\b(start|begin)\s+(the\s+)?onboarding\s+(process|workflow|checklist)\b|"
    r"\bstart_onboarding\b"
    r")",
    re.I,
)

REPORT_RE = re.compile(
    r"("
    r"\b(recurring|weekly|daily|monthly|team|status)\s+report\b|"
    r"\breport\s+(for|on|over)\b|"
    r"\b(generate|draft|write|post|produce)\s+(a\s+|the\s+)?"
    r"(weekly\s+|daily\s+|monthly\s+|team\s+)?(report|digest)\b|"
    r"\b(weekly|daily|monthly)\s+digest\b|"
    r"\bchannel\s+digest\b|"
    r"\bdigest\s+(for|of)\s+(the\s+)?(week|channel|team)\b"
    r")",
    re.I,
)

SUMMARIZE_RE = re.compile(
    r"\b("
    r"summariz\w*|summary|recap|tl;?dr|catch me up|what did i miss|"
    r"sum up|rundown|digest"
    r")\b",
    re.I,
)

STATUS_RE = re.compile(
    r"\b("
    r"status|who said|who mentioned|who.?s working|who is working|"
    r"what.?s the latest|any update|where are we|progress on|"
    r"who.?s on|owners? of"
    r")\b",
    re.I,
)


def question_requests_workflow_advice(question: str) -> bool:
    """True when the ask also wants file-grounded operationalisation advice."""
    return bool(WORKFLOW_ADVISE_RE.search((question or "").strip()))


def question_requests_rename(question: str) -> bool:
    """True when the ask includes a file-rename intent (J10 combined asks)."""
    return bool(FILE_RENAME_BROAD_RE.search(question or ""))


def question_requests_pdf_export(question: str) -> bool:
    """True when the ask includes a PDF-export intent."""
    return bool(FILE_PDF_EXPORT_RE.search(question or ""))
