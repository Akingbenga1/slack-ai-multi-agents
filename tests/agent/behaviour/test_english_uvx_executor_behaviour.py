"""System-behaviour tests for English plan steps + Executor real uvx CLI.

Maps 1:1 to Behaviours 1–5 in ``complaints-of-feature.Md``.
CLI ``tool_registry`` is not used for this path.
No package allowlist in this feature.

``uvx`` means the real Astral ``uv`` tool-runner binary (``uvx`` / ``uv tool run``).
Stub only the LLM script — never replace ``uvx`` with a fake installer.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from api.app.agent.base import AgentContext
from api.app.agent.factory import get_agent
from api.app.agent.llm import LlmResult, ToolCall
from api.app.agent.uvx_runner import resolve_uvx_prefix, run_uvx
from api.app.db.models import Tenant, ToolRegistry
from api.app.db.plan_store import list_agent_plan_steps

from .conftest import run_facade

QUESTION_XLSX_TO_CSV = (
    "Convert the spreadsheet I uploaded into a CSV file."
)
ATTACHMENTS = [
    {
        "filename": "finance.xlsx",
        "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "file_id": "F_XLSX_1",
    }
]


def _english_convert_step() -> dict[str, Any]:
    return {
        "tool_name": "execute_goal",
        "arguments": {
            "instruction": "Turn the uploaded spreadsheet into CSV",
            "success_criteria": "A CSV file exists with tabular rows",
        },
        "requires_attachment": True,
        "on_precondition_fail": "Please upload a spreadsheet first.",
    }


def _uvx_smoke_step() -> dict[str, Any]:
    return {
        "tool_name": "execute_goal",
        "arguments": {
            "instruction": "Run a real uvx CLI smoke check",
            "success_criteria": "Real uvx run produces stdout evidence",
        },
        "requires_attachment": True,
        "on_precondition_fail": "Please upload a spreadsheet first.",
    }


def _cli_registry_empty(db: Session, tenant: Tenant) -> None:
    assert (
        db.query(ToolRegistry)
        .filter(
            ToolRegistry.tenant_id == tenant.id,
            ToolRegistry.kind == "cli",
        )
        .count()
        == 0
    )


def _require_real_uvx() -> list[str]:
    prefix = resolve_uvx_prefix()
    if prefix is None:
        pytest.skip("real uvx/uv not on PATH")
    return prefix


class _PlanThenReactModel:
    """First complete() returns a plan; later completes drive ReAct tool calls."""

    def __init__(
        self,
        plan_steps: list[dict[str, Any]],
        react_calls: list[ToolCall] | None = None,
    ) -> None:
        self._plan_steps = plan_steps
        self._react_calls = list(react_calls or [])
        self._phase = "plan"
        self.uvx_tool_rounds = 0

    def complete(self, **kwargs: Any) -> LlmResult:
        tools = kwargs.get("tools") or []
        tool_names = {getattr(t, "name", None) for t in tools}
        if self._phase == "plan" and "run_uvx" not in tool_names:
            self._phase = "exec"
            return LlmResult(
                text=json.dumps({"workflow": "qa", "steps": self._plan_steps}),
                model="stub-plan",
                input_tokens=1,
                output_tokens=1,
            )
        # ReAct or final compose
        if "run_uvx" in tool_names:
            self.uvx_tool_rounds += 1
            if self._react_calls:
                call = self._react_calls.pop(0)
                return LlmResult(
                    text="",
                    model="stub-react",
                    input_tokens=1,
                    output_tokens=1,
                    tool_calls=(call,),
                )
            return LlmResult(
                text="Goal completed.",
                model="stub-react",
                input_tokens=1,
                output_tokens=1,
            )
        return LlmResult(
            text="All steps completed.",
            model="stub-compose",
            input_tokens=1,
            output_tokens=1,
        )


def _run_with_model(
    db: Session,
    tenant: Tenant,
    question: str,
    model: _PlanThenReactModel,
    *,
    attachments: list[dict[str, Any]] | None = None,
    tools: dict[str, Any] | None = None,
):
    from api.app.agent.facade import plan_and_execute

    return plan_and_execute(
        client_id=str(tenant.id),
        question=question,
        attachments=attachments,
        extra={"db": db, "chat_model": model, "tools": tools or {}},
    )


# ── Behaviour 1 ──


class TestBehaviour1OrchestratorEnglishWithoutRegistry:
    """Orchestrator plans English goals without a CLI registry shortlist."""

    def test_plan_uses_english_instruction_not_registry_tool_id(
        self, db: Session, tenant_a: Tenant
    ):
        _cli_registry_empty(db, tenant_a)
        steps = [_english_convert_step()]
        model = _PlanThenReactModel(steps, react_calls=[])
        # Orchestrator-only check: empty react means execute_goal fails softly,
        # but plan persistence is what this behaviour asserts.
        orch = get_agent("orchestrator").run(
            AgentContext(
                client_id=str(tenant_a.id),
                question=QUESTION_XLSX_TO_CSV,
                attachments=ATTACHMENTS,
                extra={"db": db, "chat_model": model},
            )
        )
        assert orch.status == "ready"
        plan_id = orch.extra["plan_id"]
        persisted = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan_id
        )
        assert len(persisted) >= 1
        first = persisted[0]
        args = first.arguments or {}
        instruction = (
            str(args.get("instruction") or args.get("text") or args.get("goal") or "")
            .strip()
            .lower()
        )
        assert instruction, "work step must carry a plain-English instruction"
        assert first.tool_name not in {"csvkit", "in2csv"}
        assert first.tool_name == "execute_goal"
        assert "spreadsheet" in instruction or "csv" in instruction


# ── Behaviour 2 ──


class TestBehaviour2ExecutorUsesRealUvxNotRegistry:
    """Executor shells out to real uvx; empty CLI registry must not cause tool-not-found."""

    def test_real_uvx_invoked_without_registry_lookup_failure(
        self, db: Session, tenant_a: Tenant, tmp_path: Path
    ):
        _cli_registry_empty(db, tenant_a)
        _require_real_uvx()
        uvx_cmds: list[list[str]] = []

        def tracking_run_uvx(arguments: dict[str, Any]) -> dict[str, Any]:
            package = str(arguments.get("package") or "")
            args_list = list(arguments.get("args_list") or [])
            result = run_uvx(package, args_list, cwd=tmp_path)
            uvx_cmds.append(result.cmd)
            return result.as_dict()

        model = _PlanThenReactModel(
            [_uvx_smoke_step()],
            react_calls=[
                ToolCall(
                    name="run_uvx",
                    arguments={
                        "package": "cowsay",
                        "args_list": ["-t", "hello-from-real-uvx"],
                    },
                    id="c1",
                )
            ],
        )
        result = _run_with_model(
            db,
            tenant_a,
            QUESTION_XLSX_TO_CSV,
            model,
            attachments=ATTACHMENTS,
            tools={"run_uvx": tracking_run_uvx},
        )
        assert "tool not found" not in (result.message or "").lower()
        assert uvx_cmds, "Executor must invoke real uvx"
        assert uvx_cmds[0][0] in {"uvx", "uv"} or "uv" in uvx_cmds[0][0]
        assert result.status == "succeeded"


# ── Behaviour 3 ──


class TestBehaviour3ReactRetryOnRealUvxFailure:
    """Failed first real uvx guess retries inside the ReAct loop."""

    def test_second_real_uvx_attempt_after_nonzero_exit(
        self, db: Session, tenant_a: Tenant, tmp_path: Path
    ):
        _cli_registry_empty(db, tenant_a)
        _require_real_uvx()
        attempts: list[dict[str, Any]] = []

        def tracking_run_uvx(arguments: dict[str, Any]) -> dict[str, Any]:
            package = str(arguments.get("package") or "")
            args_list = list(arguments.get("args_list") or [])
            result = run_uvx(package, args_list, cwd=tmp_path)
            payload = result.as_dict()
            attempts.append(payload)
            return payload

        model = _PlanThenReactModel(
            [_uvx_smoke_step()],
            react_calls=[
                ToolCall(
                    name="run_uvx",
                    arguments={
                        "package": "this-package-definitely-does-not-exist-xyzzy-9f3a",
                        "args_list": ["--help"],
                    },
                    id="c1",
                ),
                ToolCall(
                    name="run_uvx",
                    arguments={
                        "package": "cowsay",
                        "args_list": ["-t", "retry-ok"],
                    },
                    id="c2",
                ),
            ],
        )
        result = _run_with_model(
            db,
            tenant_a,
            QUESTION_XLSX_TO_CSV,
            model,
            attachments=ATTACHMENTS,
            tools={"run_uvx": tracking_run_uvx},
        )
        assert len(attempts) >= 2
        assert attempts[0]["ok"] is False
        assert attempts[1]["ok"] is True
        plan_id = result.extra["plan_id"]
        steps = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan_id
        )
        assert steps
        payload = steps[0].result if isinstance(steps[0].result, dict) else {}
        assert int(payload.get("attempt_count") or 0) >= 2
        assert result.status == "succeeded"


# ── Behaviour 4 ──


class TestBehaviour4BadPackageFailsViaRealUvxNotRegistry:
    """Nonsense package fails through real uvx/PyPI — not tool_registry or allowlist."""

    def test_missing_package_errors_from_uvx_not_registry(
        self, db: Session, tenant_a: Tenant, tmp_path: Path
    ):
        _cli_registry_empty(db, tenant_a)
        _require_real_uvx()

        def tracking_run_uvx(arguments: dict[str, Any]) -> dict[str, Any]:
            return run_uvx(
                str(arguments.get("package") or ""),
                list(arguments.get("args_list") or []),
                cwd=tmp_path,
            ).as_dict()

        model = _PlanThenReactModel(
            [_uvx_smoke_step()],
            react_calls=[
                ToolCall(
                    name="run_uvx",
                    arguments={
                        "package": "this-package-definitely-does-not-exist-xyzzy-9f3a",
                        "args_list": ["--version"],
                    },
                    id="c1",
                )
            ],
        )
        result = _run_with_model(
            db,
            tenant_a,
            QUESTION_XLSX_TO_CSV,
            model,
            attachments=ATTACHMENTS,
            tools={"run_uvx": tracking_run_uvx},
        )
        message = (result.message or "").lower()
        assert "tool not found" not in message
        assert "allowlist" not in message
        assert result.status == "failed"


# ── Behaviour 5 ──


class TestBehaviour5SuccessfulEnglishStepYieldsRealCliOutput:
    """Successful English step records evidence from real uvx without registry rows."""

    def test_succeeded_step_has_stdout_from_real_uvx(
        self, db: Session, tenant_a: Tenant, tmp_path: Path
    ):
        _cli_registry_empty(db, tenant_a)
        _require_real_uvx()
        marker = "uvx-behaviour-5-ok"

        def tracking_run_uvx(arguments: dict[str, Any]) -> dict[str, Any]:
            return run_uvx(
                str(arguments.get("package") or ""),
                list(arguments.get("args_list") or []),
                cwd=tmp_path,
            ).as_dict()

        model = _PlanThenReactModel(
            [_uvx_smoke_step()],
            react_calls=[
                ToolCall(
                    name="run_uvx",
                    arguments={
                        "package": "cowsay",
                        "args_list": ["-t", marker],
                    },
                    id="c1",
                )
            ],
        )
        result = _run_with_model(
            db,
            tenant_a,
            QUESTION_XLSX_TO_CSV,
            model,
            attachments=ATTACHMENTS,
            tools={"run_uvx": tracking_run_uvx},
        )
        assert result.status == "succeeded"
        plan_id = result.extra["plan_id"]
        steps = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan_id
        )
        assert steps, "plan must persist steps"
        evidence = ""
        for step in steps:
            if step.status != "succeeded":
                continue
            payload = step.result if isinstance(step.result, dict) else {}
            evidence = str(
                payload.get("stdout")
                or payload.get("output_file")
                or payload.get("output_path")
                or ""
            )
            if evidence:
                break
        combined = f"{evidence}\n{result.message or ''}"
        assert marker in combined
        assert (
            db.query(ToolRegistry)
            .filter(
                ToolRegistry.tenant_id == tenant_a.id,
                ToolRegistry.kind == "cli",
            )
            .count()
            == 0
        ), "success must not require CLI tool_registry rows"
