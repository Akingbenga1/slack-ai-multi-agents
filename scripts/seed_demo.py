"""Seed demo roles, tenant, and memberships (idempotent)."""

from api.app.db.session import SessionLocal
from api.app.membership import ensure_demo_memberships


def main() -> None:
    db = SessionLocal()
    try:
        ensure_demo_memberships(db)
        print("Demo memberships seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
