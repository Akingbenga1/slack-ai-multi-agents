"""Facade invariants for the Deep Agents harness entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from api.app.agent.base import AgentResult
from api.app.agent.facade import plan_and_execute
from api.app.membership import DEMO_TENANT_ID


def _fake_harness_runner(**kwargs: Any) -> AgentResult:
    client_id = str(kwargs.get("client_id") or "")
    question = str(kwargs.get("question") or "")
    attachments = list(kwargs.get("attachments") or [])
    extra = dict(kwargs.get("extra") or {})
    delivered: list[str] = []
    if attachments:
        local = str(attachments[0].get("local_path") or "")
        if local:
            out = Path(local).with_name("harness-output.txt")
            out.write_text(f"done:{question[:40]}", encoding="utf-8")
            delivered = [str(out.resolve())]
    status = "succeeded" if delivered or "fail" not in question.lower() else "failed"
    return AgentResult(
        role="facade",
        client_id=client_id,
        status=status,
        message="ok" if status == "succeeded" else "failed on purpose",
        extra={
            "plan_id": str(uuid4()),
            "run_id": str(uuid4()),
            "phase": "harness",
            "workflow": "deep_agents",
            "delivered_files": delivered,
            "step_diagnostics": [
                {
                    "step_index": 0,
                    "tool_name": "deep_agents",
                    "status": status,
                    "verification_method": "injected",
                    "verification_reason": "test double",
                }
            ],
            **(
                {
                    "orchestrator_user_prompt": question,
                    "plan_steps": [],
                    "planner_raw": "{}",
                }
                if extra.get("include_trace")
                else {}
            ),
        },
    )


def test_facade_uses_harness_runner(tmp_path: Path) -> None:
    src = tmp_path / "note.txt"
    src.write_text("hello", encoding="utf-8")
    result = plan_and_execute(
        client_id=str(DEMO_TENANT_ID),
        question="turn this into an output",
        attachments=[
            {
                "filename": "note.txt",
                "local_path": str(src),
            }
        ],
        extra={"harness_runner": _fake_harness_runner, "include_trace": True},
    )
    assert result.status == "succeeded"
    assert result.extra["phase"] == "harness"
    assert result.extra["workflow"] == "deep_agents"
    assert result.extra["delivered_files"]
    assert result.extra.get("orchestrator_user_prompt")


def test_facade_harness_failure_path() -> None:
    result = plan_and_execute(
        client_id=str(DEMO_TENANT_ID),
        question="please fail this run",
        extra={"harness_runner": _fake_harness_runner},
    )
    assert result.status == "failed"
    assert result.extra["phase"] == "harness"
