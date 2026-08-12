"""Sprint 22.1 — first-org hardening smoke (fixtures; no live Stripe/Slack).

Examples:
  DEMO_ACTIVATE_PLAN=true uv run python scripts/seed_demo.py
  uv run python scripts/first_org_hardening_smoke.py

  uv run pytest tests/demo/test_first_org_hardening.py -q
"""

from __future__ import annotations

import json
import sys

from sqlalchemy import select

from api.app.billing.plans import apply_plan_state, require_entitlement, tenant_has_entitlement
from api.app.db.models import BillingCustomer
from api.app.db.session import SessionLocal
from api.app.demo.readiness import demo_readiness
from api.app.governance.budgets import check_budget
from api.app.membership import DEMO_TENANT_ID, ensure_demo_memberships
from api.app.settings import get_settings


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def run_db_smoke() -> dict:
    settings = get_settings()
    db = SessionLocal()
    try:
        ensure_demo_memberships(db)
        db.expire_all()
        payload = demo_readiness(db, tenant_id=DEMO_TENANT_ID)
        _assert(payload["checks"]["tenant_exists"], "demo tenant missing")
        _assert(payload["checks"]["billing_row"], "billing row missing")
        _assert(payload["checks"]["agent_config"], "agent_config missing")

        row = db.scalar(
            select(BillingCustomer).where(BillingCustomer.tenant_id == DEMO_TENANT_ID)
        )
        assert row is not None

        apply_plan_state(db, row, plan_status="inactive", clear_subscription=True)
        db.commit()
        _assert(
            not tenant_has_entitlement(db, DEMO_TENANT_ID, "sync"),
            "inactive should deny sync",
        )
        denied = check_budget(
            db, DEMO_TENANT_ID, "jobs", units=1, require_active_plan=True
        )
        _assert(
            not denied.allowed and denied.reason == "plan_inactive",
            "budget must deny inactive",
        )

        try:
            require_entitlement(db, DEMO_TENANT_ID, "ingest")
            raise AssertionError("require_entitlement should raise when inactive")
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            detail = getattr(exc, "detail", None)
            ok = status_code == 403 or (
                isinstance(detail, dict) and detail.get("detail") == "entitlement_denied"
            )
            _assert(ok, f"expected 403 entitlement_denied, got {exc!r}")

        apply_plan_state(
            db,
            row,
            plan_status="active",
            external_subscription_id="sub_smoke_local",
            extra_meta={"source": "first_org_hardening_smoke"},
        )
        db.commit()
        _assert(
            tenant_has_entitlement(db, DEMO_TENANT_ID, "agent"),
            "active should grant agent",
        )
        allowed = check_budget(
            db, DEMO_TENANT_ID, "jobs", units=1, require_active_plan=True
        )
        _assert(allowed.allowed, "active plan should allow jobs budget")

        if settings.demo_activate_plan:
            apply_plan_state(
                db,
                row,
                plan_status="active",
                extra_meta={"source": "demo_seed"},
            )
            db.commit()

        payload = demo_readiness(db, tenant_id=DEMO_TENANT_ID)
        payload["smoke"] = {
            "inactive_deny_ok": True,
            "active_allow_ok": True,
            "demo_activate_plan_env": settings.demo_activate_plan,
        }
        return payload
    finally:
        db.close()


def main() -> int:
    try:
        payload = run_db_smoke()
    except Exception as exc:
        print(f"first_org_hardening_smoke_failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, default=str))
    if not payload.get("ready_for_paid_demo"):
        print(
            "note: ready_for_paid_demo=false — set DEMO_ACTIVATE_PLAN=true and re-seed, "
            "or complete Stripe Checkout (see docs/demo-readiness.md)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
