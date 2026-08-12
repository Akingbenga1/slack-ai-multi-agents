"""Mention/DM → grounded agent reply (Sprint 14) + file actions (Sprint 23).

Sprint 26: orchestration delegates to ``reply_pipeline`` (Gate → Intake →
RunAgent → Deliver). Entitlement helpers remain here for routes/tests.
Agent invoke goes through ``run_agent`` / ``AgentRuntime`` (Sprint 39) — no
LangGraph types in this module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.billing.plans import plan_is_active, tenant_has_entitlement, tenant_is_suspended
from api.app.governance.budgets import BudgetDecision, check_budget
from api.app.settings import Settings
from api.app.slack.files import MSG_FILE_JOB_DENIED
from api.app.slack.reply_pipeline import run_reply_pipeline

MSG_PLAN_INACTIVE = (
    "Your organisation's plan is inactive, so I can't answer right now. "
    "An admin can renew billing in the org portal to restore agent replies."
)

MSG_TENANT_SUSPENDED = (
    "Your organisation is suspended on the platform, so I can't answer right now. "
    "Contact the platform owner for support."
)

MSG_AGENT_DISABLED = (
    "Agent replies are not enabled for your organisation's plan. "
    "Ask an admin to check entitlements in the org portal."
)

MSG_BUDGET_EXCEEDED = (
    "Your organisation has reached its {window} {resource} budget "
    "(used {used} of {limit}). Try again later, or ask an admin to review usage."
)

MSG_NO_BUDGET = (
    "Your organisation has no token budget configured, so I can't answer right now. "
    "Ask an admin to check the plan in the org portal."
)

WORKFLOW_LIBRARY_WORKFLOWS = frozenset(
    {"workflow_store", "workflow_list", "workflow_copy", "workflow_edit"}
)


def entitlement_slack_message(decision: BudgetDecision) -> str:
    """Clear Slack copy when plan/budget blocks the agent."""
    if decision.reason == "plan_inactive":
        return MSG_PLAN_INACTIVE
    if decision.reason == "no_budget":
        return MSG_NO_BUDGET
    if decision.reason == "budget_exceeded":
        return MSG_BUDGET_EXCEEDED.format(
            window=decision.window or "current",
            resource=decision.resource,
            used=decision.used,
            limit=decision.limit,
        )
    return MSG_PLAN_INACTIVE


def check_agent_entitlement(
    db: Session,
    tenant_id: UUID | str,
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """
    Allow agent path only for active plan with agent entitlement + token headroom.

    Returns (allowed, denial_message). denial_message is empty when allowed.
    """
    tid = UUID(str(tenant_id))
    if tenant_is_suspended(db, tid):
        return False, MSG_TENANT_SUSPENDED
    if not plan_is_active(db, tid):
        return False, MSG_PLAN_INACTIVE
    if not tenant_has_entitlement(db, tid, "agent"):
        return False, MSG_AGENT_DISABLED

    decision = check_budget(
        db,
        tid,
        "tokens",
        units=1,
        now=now,
        require_active_plan=True,
    )
    if not decision.allowed:
        return False, entitlement_slack_message(decision)
    return True, ""


def check_file_job_entitlement(
    db: Session,
    tenant_id: UUID | str,
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """
    Extra gate for heavy file/PDF jobs (jobs_daily budget + agent plan).

    Returns (allowed, denial_message).
    """
    tid = UUID(str(tenant_id))
    allowed, denial = check_agent_entitlement(db, tid, now=now)
    if not allowed:
        return False, denial

    decision = check_budget(
        db,
        tid,
        "jobs",
        units=1,
        now=now,
        require_active_plan=True,
    )
    if not decision.allowed:
        reason = entitlement_slack_message(decision)
        return False, MSG_FILE_JOB_DENIED.format(reason=reason)
    return True, ""


def process_agent_reply(
    *,
    tenant_id: UUID | str,
    bot_token: str,
    event: dict[str, Any],
    team_id: str | None = None,
    settings: Settings | None = None,
    db_factory: Optional[Callable[[], Session]] = None,
    run_agent_fn: Optional[Callable[..., dict[str, Any]]] = None,
    post_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Gate → Intake → RunAgent → Deliver (Sprint 26 pipeline).

    Designed to run in a FastAPI BackgroundTask with a fresh DB session.
    """
    return run_reply_pipeline(
        tenant_id=tenant_id,
        bot_token=bot_token,
        event=event,
        team_id=team_id,
        settings=settings,
        db_factory=db_factory,
        run_agent_fn=run_agent_fn,
        post_fn=post_fn,
        check_agent_entitlement=check_agent_entitlement,
        check_file_job_entitlement=check_file_job_entitlement,
    )
