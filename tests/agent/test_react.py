"""ReAct harness: token budget, never-ran calls, and diagnostic stops."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from api.app.agent.llm import LlmResult, ToolCall
from api.app.agent.react import StepBudget, StepRequest, run_goal_step
from api.app.agent.workspace import create_run_workspace
from api.app.settings import Settings


class ScriptedModel:
    def __init__(self, responses: list[LlmResult]) -> None:
        self.responses = list(responses)
        self.max_tokens_seen: list[int | None] = []

    def complete(self, **kwargs: Any) -> LlmResult:
        self.max_tokens_seen.append(kwargs.get("max_tokens"))
        if self.responses:
            return self.responses.pop(0)
        return LlmResult(
            text="",
            model="stub",
            input_tokens=1,
            output_tokens=1,
            tool_calls=(
                ToolCall(
                    name="finish",
                    arguments={"status": "blocked", "answer": "stopped"},
                    id="done",
                ),
            ),
        )


def _call(name: str, arguments: dict[str, Any], *, call_id: str = "c") -> LlmResult:
    return LlmResult(
        text="",
        model="stub",
        input_tokens=1,
        output_tokens=1,
        tool_calls=(ToolCall(name=name, arguments=arguments, id=call_id),),
    )


def _run(tmp_path: Path, model: ScriptedModel, **budget_kwargs: Any) -> dict[str, Any]:
    workspace = create_run_workspace(
        client_id="t", run_key="r", attachments=[], base_dir=tmp_path
    )
    settings = Settings(executor_uvx_max_attempts=4, executor_empty_continuations=1)
    return run_goal_step(
        StepRequest(
            instruction="Write a file",
            success_criteria="A new file exists",
            question="Write a file",
            workspace=workspace,
            model=model,
            settings=settings,
            budget=StepBudget(max_actions=4, max_rounds=8, max_malformed=3, **budget_kwargs),
            action_overrides={
                "run_python": lambda args: (
                    {
                        "ok": False,
                        "tool": "run_python",
                        "error": "script is required",
                        "error_class": "invalid_action",
                    }
                    if not str(args.get("script") or "").strip()
                    else {"ok": True, "tool": "run_python", "stdout": "wrote"}
                )
            },
        )
    )


def test_empty_script_is_never_ran_not_a_repeat(tmp_path: Path) -> None:
    model = ScriptedModel(
        [
            _call("run_python", {"libs": []}, call_id="1"),
            _call("run_python", {"libs": []}, call_id="2"),
            _call("run_python", {"script": "print('ok')", "libs": []}, call_id="3"),
            _call(
                "finish",
                {"status": "success", "answer": "done"},
                call_id="4",
            ),
        ]
    )
    result = _run(tmp_path, model)
    classes = [a.get("error_class") for a in result["attempts"]]
    assert classes.count("invalid_action") == 2
    assert "refused" not in classes
    assert result["malformed_count"] == 2
    assert any(a.get("ok") and a.get("tool") == "run_python" for a in result["attempts"])


def test_malformed_budget_stops_with_diagnostic_reason(tmp_path: Path) -> None:
    model = ScriptedModel(
        [
            _call("run_python", {}, call_id="1"),
            _call("run_python", {}, call_id="2"),
            _call("run_python", {}, call_id="3"),
        ]
    )
    result = _run(tmp_path, model)
    assert result.get("ok") is False
    assert result.get("stop_reason") == "no progress: malformed actions"
    assert "identical action already attempted" not in str(result.get("error") or "")


def test_executor_passes_its_own_token_budget(tmp_path: Path) -> None:
    model = ScriptedModel(
        [
            _call(
                "finish",
                {"status": "blocked", "answer": "cannot"},
                call_id="1",
            )
        ]
    )
    _run(tmp_path, model, max_tokens=8192)
    assert 8192 in model.max_tokens_seen
