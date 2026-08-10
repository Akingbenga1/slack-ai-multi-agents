"""Sprint 22.4 — second org stand-up + knowledge isolation smoke.

Creates (or reuses) a second tenant via admin provision, then proves Qdrant
search never returns the other tenant's points (in-memory always; live Qdrant
optional).

Examples:
  uv run python scripts/seed_demo.py
  uv run python scripts/second_org_smoke.py
  uv run pytest tests/demo/test_second_org.py -q
"""

from __future__ import annotations

import json
import sys

from api.app.admin.provision import ensure_organisation
from api.app.admin.tenants import list_tenant_summaries
from api.app.db.session import SessionLocal
from api.app.demo.isolation import prove_no_knowledge_leak
from api.app.membership import DEMO_TENANT_ID, ensure_demo_memberships
from api.app.settings import get_settings

SECOND_SLUG = "second-org"
SECOND_EMAIL = "admin-second@example.com"
SECOND_PASSWORD = "second123"
SECOND_NAME = "Second Organisation"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def run_smoke() -> dict:
    settings = get_settings()
    db = SessionLocal()
    try:
        ensure_demo_memberships(db)
        db.expire_all()
        second = ensure_organisation(
            db,
            name=SECOND_NAME,
            slug=SECOND_SLUG,
            admin_email=SECOND_EMAIL,
            admin_password=SECOND_PASSWORD,
            activate_plan=True,
            actor_email="second_org_smoke",
            settings=settings,
        )
        summaries = list_tenant_summaries(db)
        ids = {s["id"] for s in summaries}
        _assert(str(DEMO_TENANT_ID) in ids, "demo tenant missing from admin list")
        _assert(str(second.tenant.id) in ids, "second org missing from admin list")
        _assert(
            str(second.tenant.id) != str(DEMO_TENANT_ID),
            "second org must be a distinct tenant_id",
        )

        isolation = prove_no_knowledge_leak(
            tenant_a=str(DEMO_TENANT_ID),
            tenant_b=str(second.tenant.id),
            settings=settings,
        )
        return {
            "demo_tenant_id": str(DEMO_TENANT_ID),
            "second_tenant_id": str(second.tenant.id),
            "second_slug": second.tenant.slug,
            "second_admin_email": second.admin.email,
            "second_created": second.created,
            "tenant_count": len(summaries),
            "isolation": isolation,
            "ok": True,
        }
    finally:
        db.close()


def main() -> int:
    try:
        payload = run_smoke()
    except Exception as exc:
        print(f"second_org_smoke_failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
