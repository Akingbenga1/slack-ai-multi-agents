"""Generic model-tier policy (Sprint 13.3 / 33.3).

Graph uses ``fast`` / ``capable`` only. Concrete vendor model ids are
resolved inside each LLM adapter — not here.
"""

from __future__ import annotations

import re
from typing import Iterable

from api.app.agent.state import ModelTier

_COMPLEXITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("compare", re.compile(r"\b(compare|contrast|versus|vs\.?)\b", re.I)),
    ("analyze", re.compile(r"\b(analy[sz]e|deep.?dive|trade-?off|synthesize)\b", re.I)),
    ("multi_part", re.compile(r"\b(first|second|third|also|additionally)\b.*\?", re.I | re.S)),
    ("long_form", re.compile(r".{400,}", re.S)),
]

_ESCALATE_WORKFLOWS: frozenset[str] = frozenset(
    {
        "summarize",
        "status",
        "meeting_brief",
        "meeting_agenda",
        "meeting_notes",
        "report",
        "file_analyse",
        "file_pdf_export",
        "workflow_advise",
    }
)


def detect_complexity_flags(
    question: str,
    *,
    workflow: str = "qa",
) -> list[str]:
    """Return complexity flag names that justify capable-tier escalation."""
    text = (question or "").strip()
    flags: list[str] = []
    if workflow in _ESCALATE_WORKFLOWS:
        flags.append(f"workflow:{workflow}")
    for name, pattern in _COMPLEXITY_PATTERNS:
        if text and pattern.search(text):
            flags.append(name)
    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def choose_model_tier(
    *,
    flags: Iterable[str] | None = None,
    default: ModelTier = "fast",
) -> ModelTier:
    """Default fast; escalate to capable when any complexity flag is set."""
    if flags and any(flags):
        return "capable"
    return default
