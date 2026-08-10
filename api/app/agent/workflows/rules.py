"""Ordered classifier rules — Strategy / Chain-of-Responsibility (Sprint 25.3).

Each rule is a small Strategy: ``matches(question, has_attachments) -> bool``.
``classify_workflow`` walks the ordered list and returns the first hit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Protocol

from api.app.agent.state import WorkflowName
from api.app.agent.workflows import intents


class ClassifierRule(Protocol):
    """Strategy contract for one workflow classification rule."""

    name: WorkflowName

    def matches(self, question: str, *, has_attachments: bool = False) -> bool:
        ...


@dataclass(frozen=True)
class RegexRule:
    """Match when a compiled regex finds a hit in the question text."""

    name: WorkflowName
    pattern: re.Pattern[str]

    def matches(self, question: str, *, has_attachments: bool = False) -> bool:
        _ = has_attachments
        return bool(self.pattern.search(question))


@dataclass(frozen=True)
class PredicateRule:
    """Match when a custom predicate returns True (attachment heuristics, etc.)."""

    name: WorkflowName
    predicate: Callable[[str, bool], bool]

    def matches(self, question: str, *, has_attachments: bool = False) -> bool:
        return bool(self.predicate(question, has_attachments))


def _pdf_export_rule(question: str, _has_attachments: bool) -> bool:
    # Prefer PDF when export intent is present (incl. analyse+PDF / rename+PDF).
    return bool(intents.FILE_PDF_EXPORT_RE.search(question))


def _file_rename_only(question: str, _has_attachments: bool) -> bool:
    # Rename alone — not when analyse is also requested (analyse wins later;
    # PDF already handled above). Preserve prior ladder semantics.
    return bool(
        intents.FILE_RENAME_RE.search(question)
        and not intents.FILE_ANALYSE_RE.search(question)
    )


def _file_analyse_rule(question: str, _has_attachments: bool) -> bool:
    return bool(intents.FILE_ANALYSE_RE.search(question))


def _attachment_heuristic(question: str, has_attachments: bool) -> bool:
    if not has_attachments:
        return False
    return bool(intents.ATTACHMENT_CUE_RE.search(question))


# Order matches the former route.py ladder (library → file → meeting → … → qa).
CLASSIFIER_RULES: tuple[ClassifierRule, ...] = (
    RegexRule("workflow_store", intents.WORKFLOW_STORE_RE),
    RegexRule("workflow_copy", intents.WORKFLOW_COPY_RE),
    RegexRule("workflow_edit", intents.WORKFLOW_EDIT_RE),
    RegexRule("workflow_list", intents.WORKFLOW_LIST_RE),
    RegexRule("workflow_advise", intents.WORKFLOW_ADVISE_RE),
    PredicateRule("file_pdf_export", _pdf_export_rule),
    PredicateRule("file_rename", _file_rename_only),
    PredicateRule("file_analyse", _file_analyse_rule),
    PredicateRule("file_analyse", _attachment_heuristic),
    RegexRule("meeting_agenda", intents.MEETING_AGENDA_RE),
    RegexRule("meeting_notes", intents.MEETING_NOTES_RE),
    RegexRule("meeting_brief", intents.MEETING_BRIEF_RE),
    RegexRule("onboarding", intents.ONBOARDING_RE),
    RegexRule("report", intents.REPORT_RE),
    RegexRule("summarize", intents.SUMMARIZE_RE),
    RegexRule("status", intents.STATUS_RE),
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
    for rule in CLASSIFIER_RULES:
        if rule.matches(text, has_attachments=has_attachments):
            return rule.name
    return "qa"
