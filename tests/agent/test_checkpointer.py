"""Postgres checkpointer helpers (Task 13.2)."""

from api.app.agent.checkpointer import to_psycopg_conninfo, thread_id_for_tenant


def test_to_psycopg_conninfo_strips_sqlalchemy_driver():
    url = "postgresql+psycopg://csa:csa@localhost:5433/csa"
    assert to_psycopg_conninfo(url) == "postgresql://csa:csa@localhost:5433/csa"


def test_thread_id_for_tenant_normalizes_uuid():
    tid = thread_id_for_tenant(
        "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA",
        "conv-1",
    )
    assert tid == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa:conv-1"
