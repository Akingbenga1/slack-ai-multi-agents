"""ReAct engine for one plain-English goal.

The engine owns an append-only transcript in the provider-neutral tool-calling
format: every requested action is answered by exactly one observation, so the
history stays valid for the provider and remains cacheable across rounds.

Termination is explicit. The model ends a step by calling ``finish``; the loop
otherwise stops only when a declared budget is spent (actions, rounds, or wall
clock) or when it detects that it is repeating itself. Repeated identical
actions are refused rather than re-run, and a run of failures triggers one
structured self-review before further attempts, so a stuck step changes
strategy instead of consuming its budget on the same call.

A ``finish`` call is a claim, not proof: the payload is handed to independent
outcome verification, which decides whether the contract was met.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from api.app.agent.code_exec import (
    FINISH_ACTION,
    INSPECT_ACTION,
    RUN_CLI_ACTION,
    RUN_PYTHON_ACTION,
    inspect_workspace,
    run_cli,
    run_python,
)
from api.app.agent.llm import (
    ChatModel,
    EMPTY_COMPLETION_TEXT,
    TOOL_CHOICE_AUTO,
    TOOL_CHOICE_NONE,
    TOOL_CHOICE_REQUIRED,
    ToolCall,
    ToolSchema,
    assistant_action_message,
    tool_observation_message,
)
from api.app.agent.outcome_verifier import verify_step_outcome
from api.app.agent.workspace import RunWorkspace
from api.app.logging_config import get_logger

logger = get_logger("api.agent.react")

SYSTEM_PROMPT = (
    "You are an execution agent. You receive one goal at a time and must "
    "achieve it inside an isolated workspace using the available actions.\n\n"
    "Workspace rules:\n"
    "- The workspace is your working directory. Address every file by a "
    "relative path with forward slashes; absolute paths and paths outside the "
    "workspace are rejected.\n"
    "- Declared inputs are already staged in the workspace as copies. The "
    "user's originals are untouched, so you may read inputs freely, but write "
    "results to new files rather than overwriting an input.\n\n"
    "Actions:\n"
    "1) run_python — the primary action. You write a Python script and it runs "
    "under `uvx --with <libs> python`, so any PyPI library is available: name "
    "each distribution you import in `libs`. Prefer this for document, "
    "spreadsheet, image, archive, data, and text work.\n"
    "2) run_uvx — run a PyPI console script when a dedicated command-line tool "
    "is genuinely the better instrument. Set `package` to the executable and "
    "`from_spec` to the install name when they differ.\n"
    "3) inspect_workspace — list files and peek at text content. Use it to "
    "ground yourself instead of guessing about names, shapes, or formats.\n"
    "4) finish — end the step. Call it exactly once, when the goal is met or "
    "when you are certain it cannot be.\n\n"
    "How to work:\n"
    "- Import names and distribution names differ: `libs` takes the "
    "distribution (import fitz → pymupdf, import PIL → pillow, import docx → "
    "python-docx, import pptx → python-pptx, import bs4 → beautifulsoup4).\n"
    "- Have your script print what it did and the paths it wrote. Printed "
    "output is your evidence and the basis of the final answer.\n"
    "- Write scripts defensively: check what inputs actually contain before "
    "assuming a structure, and raise a clear error when an assumption fails.\n"
    "- Read every observation. `error_class` and `suggested_next` tell you "
    "whether to correct the same approach or change instrument.\n"
    "- A failing action means fix the cause, not repeat the call. Identical "
    "repeated actions are refused without running.\n"
    "- Goals that call for a file are complete only when the file exists in "
    "the workspace. Never claim an artifact you did not create.\n"
    "- Goals that call for information are complete when you have the content; "
    "pass it in the `answer` field of finish.\n"
    "- Reuse work from prior steps instead of redoing it, and confirm and stop "
    "when the goal is already satisfied."
)

_ACTION_NUDGE = (
    "Use an action to make progress, or call finish if the step is complete "
    "or cannot be completed."
)
# Requests rejected before any instrument ran. They produce no observation of
# the world, so they are not charged against the action budget.
_NON_EXECUTING_ERROR_CLASSES = frozenset({"invalid_action", "truncated_action"})
_TRUNCATION_NUDGE = (
    "The previous reply was cut off before a complete action was emitted. "
    "Call run_python again with the full source in `script`."
)
_MALFORMED_GUIDANCE = (
    "The last action never ran. Provide the complete source in `script`, "
    "or use a different instrument."
)
_MALFORMED_FINISH_GUIDANCE = (
    "Malformed actions are exhausting the budget. Call finish and report "
    "the outcome honestly."
)
_FINISH_NUDGE = (
    "Do not answer in prose. Call finish with the outcome, the answer text, "
    "and the relative paths of any files you created."
)
_REFLECT_PROMPT = (
    "Pause and self-review before acting again. In a few sentences: state why "
    "the recent attempts failed, what that rules out, and which different "
    "approach you will take next. Do not call an action in this reply."
)

RUN_PYTHON_SCHEMA = ToolSchema(
    name=RUN_PYTHON_ACTION,
    description=(
        "Run a Python script in the workspace via `uvx --with <libs> python`. "
        "The script's working directory is the workspace root; use relative "
        "paths. Print what you did and any file paths you wrote."
    ),
    parameters={
        "type": "object",
        "properties": {
            "script": {
                "type": "string",
                "description": "Complete Python source to execute.",
            },
            "libs": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "PyPI distribution names to install, e.g. ['pillow'] or "
                    "['pypdf']. Omit for standard-library-only scripts."
                ),
            },
            "purpose": {
                "type": "string",
                "description": "One line on what this script is meant to achieve.",
            },
        },
        "required": ["script"],
    },
)

RUN_CLI_SCHEMA = ToolSchema(
    name=RUN_CLI_ACTION,
    description=(
        "Run a PyPI console script via uvx in the workspace. Use when a "
        "dedicated CLI is the better instrument than a script."
    ),
    parameters={
        "type": "object",
        "properties": {
            "package": {
                "type": "string",
                "description": "Console script (executable) name to run.",
            },
            "from_spec": {
                "type": "string",
                "description": "PyPI install spec when it differs from the executable.",
            },
            "with_packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Extra distributions to install alongside.",
            },
            "args_list": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Arguments after the executable; relative paths only.",
            },
            "help_only": {
                "type": "boolean",
                "description": "Show the tool's help instead of running it.",
            },
        },
        "required": ["package"],
    },
)

INSPECT_SCHEMA = ToolSchema(
    name=INSPECT_ACTION,
    description=(
        "List workspace files and optionally peek at the start of text files."
    ),
    parameters={
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Relative paths to peek into (up to 5).",
            },
            "peek_bytes": {
                "type": "integer",
                "description": "Characters to read from each path (default 2000).",
            },
        },
    },
)

FINISH_SCHEMA = ToolSchema(
    name=FINISH_ACTION,
    description=(
        "End the step. Report whether the goal was achieved, the answer text "
        "for the user, and the relative paths of files you created."
    ),
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["success", "blocked"],
                "description": "'success' only if the goal is genuinely met.",
            },
            "answer": {
                "type": "string",
                "description": (
                    "For informational goals, the content itself. For artifact "
                    "goals, a short statement of what was produced."
                ),
            },
            "artifacts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Relative workspace paths of files you created.",
            },
        },
        "required": ["status", "answer"],
    },
)

ACTION_SCHEMAS = [RUN_PYTHON_SCHEMA, RUN_CLI_SCHEMA, INSPECT_SCHEMA, FINISH_SCHEMA]


@dataclass(frozen=True)
class StepBudget:
    """Independent ceilings on one step's execution."""

    max_actions: int = 12
    max_rounds: int = 16
    max_empty_rounds: int = 2
    max_repeats: int = 2
    max_malformed: int = 3
    reflect_after_failures: int = 3
    max_reflections: int = 2
    wall_clock_seconds: float = 900.0
    max_tokens: int = 8192
    thinking_tokens: int = 4096

    @classmethod
    def from_settings(cls, settings: Any) -> "StepBudget":
        actions = max(1, int(getattr(settings, "executor_uvx_max_attempts", 12) or 12))
        empty = max(0, int(getattr(settings, "executor_empty_continuations", 2) or 0))
        return cls(
            max_actions=actions,
            # Rounds exceed actions so refusals and nudges cannot starve the
            # step of chances to act.
            max_rounds=actions + empty + 4,
            max_empty_rounds=empty,
            max_repeats=max(
                1, int(getattr(settings, "executor_max_repeated_actions", 2) or 2)
            ),
            max_malformed=max(
                1, int(getattr(settings, "executor_max_malformed_actions", 3) or 3)
            ),
            reflect_after_failures=max(
                1, int(getattr(settings, "executor_reflect_after_failures", 3) or 3)
            ),
            wall_clock_seconds=float(
                getattr(settings, "executor_step_timeout_seconds", 900.0) or 900.0
            ),
            max_tokens=max(
                1024, int(getattr(settings, "executor_max_tokens", 8192) or 8192)
            ),
            thinking_tokens=max(
                0, int(getattr(settings, "executor_thinking_tokens", 4096) or 0)
            ),
        )


@dataclass
class StepRequest:
    """Everything one goal needs to execute."""

    instruction: str
    success_criteria: Any
    question: str
    workspace: RunWorkspace
    model: ChatModel
    settings: Any
    prior_results: str = "(none)"
    attachments: Sequence[dict[str, Any]] = ()
    budget: StepBudget | None = None
    action_overrides: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = field(
        default_factory=dict
    )
    model_tier: str = "fast"


def _action_fingerprint(call: ToolCall) -> tuple[Any, ...]:
    """Identity of an action, used to refuse exact repetition."""
    args = call.arguments or {}
    name = (call.name or "").strip()
    if name == RUN_PYTHON_ACTION:
        script = str(args.get("script") or args.get("code") or "")
        libs = tuple(sorted(str(x) for x in (args.get("libs") or [])))
        return (name, hash(script.strip()), libs)
    if name == RUN_CLI_ACTION:
        raw_args = args.get("args_list") or []
        if isinstance(raw_args, str):
            raw_args = [raw_args]
        with_packages = args.get("with_packages") or args.get("with") or []
        if isinstance(with_packages, str):
            with_packages = [with_packages]
        return (
            name,
            str(args.get("package") or ""),
            str(args.get("from_spec") or args.get("from") or ""),
            tuple(str(x) for x in raw_args),
            tuple(sorted(str(x) for x in with_packages)),
            bool(args.get("help_only") or args.get("help")),
        )
    if name == INSPECT_ACTION:
        paths = args.get("paths") or []
        if isinstance(paths, str):
            paths = [paths]
        return (name, tuple(sorted(str(x) for x in paths)))
    return (name, json.dumps(args, sort_keys=True, default=str))


def _python_script_text(call: ToolCall) -> str:
    args = call.arguments or {}
    return str(args.get("script") or args.get("code") or args.get("source") or "")


def _malformed_action_record(
    call: ToolCall, *, truncated: bool = False
) -> dict[str, Any] | None:
    """Return an observation when the call cannot reach an instrument."""
    name = (call.name or "").strip()
    if name == RUN_PYTHON_ACTION and not _python_script_text(call).strip():
        return {
            "ok": False,
            "tool": RUN_PYTHON_ACTION,
            "error": (
                "script is missing/empty — provide the complete source in `script`"
                if not truncated
                else "script was truncated before it could run"
            ),
            "error_class": "truncated_action" if truncated else "invalid_action",
            "retryable": True,
            "suggested_next": (
                _TRUNCATION_NUDGE if truncated else _MALFORMED_GUIDANCE
            ),
        }
    return None


def _format_observation(record: dict[str, Any], *, limit: int) -> str:
    """Render one action result as the observation the model reads."""
    tool = str(record.get("tool") or "action")
    lines = [
        f"{tool} ok={record.get('ok')!r} error_class={record.get('error_class')!r}"
    ]
    if record.get("exit_code") is not None:
        lines.append(f"exit_code={record.get('exit_code')!r}")
    produced = record.get("produced_relative") or []
    if produced:
        lines.append(f"files_written={list(produced)!r}")
    elif record.get("ok") and tool in (RUN_PYTHON_ACTION, RUN_CLI_ACTION):
        lines.append("files_written=[]")
    if record.get("entries") is not None:
        lines.append(f"workspace={json.dumps(record.get('entries'), default=str)}")
    if record.get("peeks"):
        lines.append(f"peeks={json.dumps(record.get('peeks'), default=str)}")
    stdout = str(record.get("stdout") or "").strip()
    if stdout:
        lines.append(f"stdout:\n{stdout}")
    stderr = str(record.get("stderr") or "").strip()
    if stderr:
        lines.append(f"stderr:\n{stderr}")
    error = str(record.get("error") or "").strip()
    if error and not stderr:
        lines.append(f"error: {error}")
    suggested = str(record.get("suggested_next") or "").strip()
    if suggested:
        lines.append(f"suggested_next: {suggested}")
    text = "\n".join(lines)
    return text if len(text) <= limit * 2 else text[: limit * 2]


def _format_success_criteria(raw: Any) -> str:
    if raw is None or raw == "":
        return "(meet the goal)"
    if isinstance(raw, str):
        return raw
    return json.dumps(raw, default=str)


def _initial_user_prompt(request: StepRequest) -> str:
    workspace = request.workspace
    return "\n".join(
        [
            f"User request: {request.question or '(not provided)'}",
            "",
            f"Goal for this step: {request.instruction}",
            f"Success criteria: {_format_success_criteria(request.success_criteria)}",
            "",
            "Workspace inputs (relative paths, already staged):",
            workspace.input_block(),
            "",
            "Results from earlier steps:",
            request.prior_results or "(none)",
            "",
            "Note: any tool or package names in the user request are hints "
            "only; choose the instrument yourself.",
        ]
    )


class StepExecution:
    """One goal's ReAct loop over the workspace action surface."""

    def __init__(self, request: StepRequest) -> None:
        self.request = request
        self.budget = request.budget or StepBudget.from_settings(request.settings)
        self.workspace = request.workspace
        self.transcript: list[dict[str, Any]] = [
            {"role": "user", "content": _initial_user_prompt(request)}
        ]
        self.actions: list[dict[str, Any]] = []
        self.baseline = self.workspace.snapshot()
        self._fingerprints: dict[tuple[Any, ...], int] = {}
        # Only actions that actually ran consume the budget; refusals are kept
        # in the trace but must not spend the step's chances to make progress.
        self._executed = 0
        self._consecutive_failures = 0
        self._reflections = 0
        self._empty_rounds = 0
        self._refusals = 0
        self._malformed = 0
        self._rejected_finish = 0
        self._finish: dict[str, Any] | None = None
        self._stop_reason: str | None = None
        self._started = time.monotonic()
        self._observation_limit = max(
            500, int(getattr(request.settings, "executor_observation_chars", 4000) or 4000)
        )

    # -- budget ---------------------------------------------------------

    def _time_left(self) -> float:
        return self.budget.wall_clock_seconds - (time.monotonic() - self._started)

    def _budget_stop(self, rounds: int) -> str | None:
        if rounds >= self.budget.max_rounds:
            return "round budget exhausted"
        if self._time_left() <= 0:
            return "step time budget exhausted"
        if self._refusals >= self.budget.max_repeats * 3:
            return "no progress: actions kept repeating"
        if self._malformed >= self.budget.max_malformed:
            return "no progress: malformed actions"
        return None

    def _actions_left(self) -> int:
        return self.budget.max_actions - self._executed

    def _tool_choice(self) -> str:
        # Force an action until something has actually run, so a step cannot
        # end on prose alone before any work is done. Once the budget is gone
        # the model must be free to call finish and report honestly.
        if self._executed == 0 and self._actions_left() > 0:
            return TOOL_CHOICE_REQUIRED
        return TOOL_CHOICE_AUTO

    # -- action dispatch ------------------------------------------------

    def _execute_action(self, call: ToolCall) -> dict[str, Any]:
        name = (call.name or "").strip()
        args = dict(call.arguments or {})
        override = self.request.action_overrides.get(name)
        if override is not None:
            result = override(args)
            record = dict(result) if isinstance(result, dict) else {"ok": False}
            record.setdefault("tool", name)
            if name == RUN_PYTHON_ACTION or name == RUN_CLI_ACTION:
                produced = self.workspace.files_since(self.baseline)
                record.setdefault(
                    "produced_relative",
                    [self.workspace.relative_of(p) for p in produced],
                )
            return record

        if name == RUN_PYTHON_ACTION:
            return run_python(
                args,
                workspace=self.workspace,
                settings=self.request.settings,
                label=str(args.get("purpose") or "step"),
            )
        if name == RUN_CLI_ACTION:
            return run_cli(
                args,
                workspace=self.workspace,
                settings=self.request.settings,
                attachments=self.request.attachments,
            )
        if name == INSPECT_ACTION:
            return inspect_workspace(
                args, workspace=self.workspace, settings=self.request.settings
            )
        return {
            "ok": False,
            "tool": name or "unknown",
            "error": f"unsupported action: {name!r}",
            "error_class": "invalid_action",
            "retryable": True,
            "suggested_next": (
                "Available actions are run_python, run_uvx, inspect_workspace, "
                "and finish."
            ),
        }

    def _refusal_record(self, call: ToolCall, reason: str, guidance: str) -> dict[str, Any]:
        self._refusals += 1
        return {
            "ok": False,
            "tool": (call.name or "").strip() or "unknown",
            "error": reason,
            "error_class": "refused",
            "retryable": True,
            "suggested_next": guidance,
            "refused": True,
        }

    def _handle_finish(self, call: ToolCall) -> dict[str, Any]:
        args = dict(call.arguments or {})
        status = str(args.get("status") or "").strip().lower()
        answer = str(args.get("answer") or "").strip()
        claimed = args.get("artifacts") or []
        if isinstance(claimed, str):
            claimed = [claimed]

        confirmed: list[str] = []
        missing: list[str] = []
        for raw in claimed:
            resolved = self.workspace.resolve_within(str(raw))
            if resolved is not None and resolved.is_file() and resolved.stat().st_size > 0:
                confirmed.append(str(resolved))
            else:
                missing.append(str(raw))

        if missing and self._rejected_finish < 1:
            self._rejected_finish += 1
            return {
                "ok": False,
                "tool": FINISH_ACTION,
                "error": f"claimed artifacts not found in workspace: {missing!r}",
                "error_class": "contract_unmet",
                "retryable": True,
                "suggested_next": (
                    "Create the claimed files in the workspace before finish, "
                    "or omit paths that do not exist."
                ),
                "confirmed_artifacts": confirmed,
                "missing_artifacts": missing,
                "ends_step": False,
            }

        produced = [
            path
            for path in self.workspace.files_since(self.baseline)
            if not self.workspace.is_internal(path)
        ]
        preview = {
            "ok": True,
            "output_files": [str(p) for p in produced],
            "produced_relative": [self.workspace.relative_of(p) for p in produced],
            "done_text": answer,
        }
        if confirmed:
            preview["output_file"] = confirmed[0]
        elif produced:
            preview["output_file"] = str(produced[0])
        check = verify_step_outcome(
            success_criteria=self.request.success_criteria,
            instruction=self.request.instruction,
            result=preview,
            scope_dir=self.workspace.root,
            known_inputs=self.workspace.input_paths,
            baseline_files=self.baseline.keys(),
        )
        if not check.verified and self._rejected_finish < 1:
            self._rejected_finish += 1
            return {
                "ok": False,
                "tool": FINISH_ACTION,
                "error": check.reason,
                "error_class": "contract_unmet",
                "retryable": True,
                "suggested_next": (
                    "The produced file does not yet meet the contract. "
                    "Adjust the work and try again before finish."
                ),
                "ends_step": False,
                "outcome": "partial",
            }

        self._finish = {
            "status": status or "blocked",
            "answer": answer,
            "confirmed_artifacts": confirmed,
            "missing_artifacts": missing,
        }
        record = {
            "ok": True,
            "tool": FINISH_ACTION,
            "probe": True,
            "status": self._finish["status"],
            "error_class": "finish",
            "retryable": False,
            "suggested_next": "",
            "confirmed_artifacts": confirmed,
            "missing_artifacts": missing,
            "ends_step": True,
        }
        if missing:
            record["stderr"] = (
                f"claimed artifacts not found in workspace: {missing!r}"
            )
        return record

    # -- reflection -----------------------------------------------------

    def _reflect(self) -> None:
        """One self-review turn to force a change of approach."""
        self._reflections += 1
        self.transcript.append({"role": "user", "content": _REFLECT_PROMPT})
        try:
            result = self.request.model.complete(
                system=SYSTEM_PROMPT,
                messages=list(self.transcript),
                model_tier=self.request.model_tier,
                tools=ACTION_SCHEMAS,
                tool_choice=TOOL_CHOICE_NONE,
                max_tokens=self.budget.max_tokens,
                thinking_tokens=self.budget.thinking_tokens or None,
            )
        except Exception:
            logger.exception("react_reflection_failed")
            self.transcript.pop()
            return
        text = (result.text or "").strip()
        if not text or text == EMPTY_COMPLETION_TEXT:
            self.transcript.pop()
            return
        self.transcript.append({"role": "assistant", "content": text})
        self._consecutive_failures = 0
        logger.info("react_reflection round=%d", self._reflections)

    # -- main loop ------------------------------------------------------

    def run(self) -> dict[str, Any]:
        rounds = 0
        nudged_finish = False

        while True:
            stop = self._budget_stop(rounds)
            if stop is not None:
                self._stop_reason = stop
                break

            if (
                self._consecutive_failures >= self.budget.reflect_after_failures
                and self._reflections < self.budget.max_reflections
            ):
                self._reflect()

            rounds += 1
            try:
                llm = self.request.model.complete(
                    system=SYSTEM_PROMPT,
                    messages=list(self.transcript),
                    model_tier=self.request.model_tier,
                    tools=ACTION_SCHEMAS,
                    tool_choice=self._tool_choice(),
                    max_tokens=self.budget.max_tokens,
                    thinking_tokens=self.budget.thinking_tokens or None,
                )
            except Exception as exc:
                logger.exception("react_model_call_failed")
                self._stop_reason = f"model call failed: {exc}"
                break

            if not llm.has_tool_calls:
                text = (llm.text or "").strip()
                if text == EMPTY_COMPLETION_TEXT:
                    text = ""
                if not text:
                    if (llm.stop_reason or "").lower() == "max_tokens":
                        self._malformed += 1
                        self.transcript.append(
                            {"role": "user", "content": _TRUNCATION_NUDGE}
                        )
                        continue
                    self._empty_rounds += 1
                    if self._empty_rounds > self.budget.max_empty_rounds:
                        self._stop_reason = EMPTY_COMPLETION_TEXT
                        break
                    self.transcript.append(
                        {"role": "user", "content": _ACTION_NUDGE}
                    )
                    continue
                self.transcript.append({"role": "assistant", "content": text})
                if not nudged_finish:
                    nudged_finish = True
                    self.transcript.append(
                        {"role": "user", "content": _FINISH_NUDGE}
                    )
                    continue
                self._finish = {
                    "status": "success",
                    "answer": text,
                    "confirmed_artifacts": [],
                    "missing_artifacts": [],
                }
                self._stop_reason = "ended without calling finish"
                break

            self.transcript.append(
                assistant_action_message(llm.text or "", llm.tool_calls)
            )

            truncated = (llm.stop_reason or "").lower() == "max_tokens"
            finished = False
            for call in llm.tool_calls:
                name = (call.name or "").strip()
                if name == FINISH_ACTION:
                    record = self._handle_finish(call)
                    finished = bool(record.get("ends_step", True))
                else:
                    record = self._run_one(call, rounds, truncated=truncated)
                self.actions.append({**record, "round": rounds})
                self.transcript.append(
                    tool_observation_message(
                        tool_call_id=call.id,
                        name=name or "unknown",
                        content=_format_observation(
                            record, limit=self._observation_limit
                        ),
                        is_error=not bool(record.get("ok")),
                    )
                )
            if finished:
                break

        return self._build_result()

    def _run_one(
        self, call: ToolCall, rounds: int, *, truncated: bool = False
    ) -> dict[str, Any]:
        """Budget and stall checks, then dispatch one non-finish action."""
        _ = rounds
        if self._actions_left() <= 0:
            return self._refusal_record(
                call,
                "action budget exhausted",
                "No attempts remain. Call finish and report the outcome honestly.",
            )
        if self._time_left() <= 0:
            return self._refusal_record(
                call,
                "step time budget exhausted",
                "Time is spent. Call finish and report the outcome honestly.",
            )

        early = _malformed_action_record(call, truncated=truncated)
        if early is not None:
            return self._record_malformed(early)

        fingerprint = _action_fingerprint(call)
        seen = self._fingerprints.get(fingerprint, 0)
        if seen >= self.budget.max_repeats:
            return self._refusal_record(
                call,
                "identical action already attempted",
                "This exact action has been tried. Change the approach, the "
                "script, or the instrument before acting again.",
            )
        self._fingerprints[fingerprint] = seen + 1
        self._executed += 1

        try:
            record = self._execute_action(call)
        except Exception as exc:
            logger.exception("react_action_failed name=%s", call.name)
            record = {
                "ok": False,
                "tool": (call.name or "").strip() or "unknown",
                "error": f"action raised: {exc}",
                "error_class": "execution_failed",
                "retryable": True,
                "suggested_next": "Adjust the approach and try a different action.",
            }

        if record.get("error_class") in _NON_EXECUTING_ERROR_CLASSES:
            # Never-executed calls must not look like a real try: undo the
            # action spend and drop the fingerprint so a later complete
            # script is not blocked as a repeat of an empty one.
            self._executed -= 1
            self._fingerprints.pop(fingerprint, None)
            return self._record_malformed(record)

        if record.get("ok"):
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
        return record

    def _record_malformed(self, record: dict[str, Any]) -> dict[str, Any]:
        """Count a never-executed call and attach escalating guidance."""
        self._malformed += 1
        remaining = self.budget.max_malformed - self._malformed
        if remaining <= 0:
            record["suggested_next"] = _MALFORMED_FINISH_GUIDANCE
        elif remaining == 1:
            record["suggested_next"] = _MALFORMED_GUIDANCE
        return record

    # -- result ---------------------------------------------------------

    def _build_result(self) -> dict[str, Any]:
        produced = [
            path
            for path in self.workspace.files_since(self.baseline)
            if not self.workspace.is_internal(path)
        ]
        claim = self._finish or {}
        answer = str(claim.get("answer") or "").strip()
        claimed_ok = str(claim.get("status") or "").lower() == "success"

        # A claim of success is only carried forward when the loop actually
        # delivered something observable; verification adjudicates the rest.
        delivered = [
            action
            for action in self.actions
            if action.get("ok") and action.get("tool") in (RUN_PYTHON_ACTION, RUN_CLI_ACTION)
        ]
        confirmed = list(claim.get("confirmed_artifacts") or [])
        named_artifacts = bool(confirmed or claim.get("missing_artifacts"))
        if named_artifacts:
            # Once specific files are named, at least one must exist; a claim
            # about files that are not there cannot stand in for evidence.
            ok = bool(claimed_ok and confirmed)
        else:
            ok = bool(claimed_ok and (produced or delivered))

        result: dict[str, Any] = {
            "ok": ok,
            "instruction": self.request.instruction,
            "attempts": self.actions,
            "attempt_count": self._executed,
            "workspace": str(self.workspace.root),
            "output_files": [str(p) for p in produced],
            "produced_relative": [self.workspace.relative_of(p) for p in produced],
        }
        if confirmed:
            result["output_file"] = confirmed[0]
        elif produced:
            result["output_file"] = str(produced[0])
        if answer:
            result["done_text"] = answer
        stdout = self._last_stdout()
        if stdout:
            result["stdout"] = stdout
        if self._stop_reason:
            result["stop_reason"] = self._stop_reason
        result["malformed_count"] = self._malformed
        if claim.get("missing_artifacts"):
            result["missing_artifacts"] = claim["missing_artifacts"]
        if not ok:
            result["error"] = self._failure_text(claim)
        logger.info(
            "react_step_done ok=%s executed=%d recorded=%d produced=%d stop=%s",
            ok,
            self._executed,
            len(self.actions),
            len(produced),
            self._stop_reason,
        )
        return result

    def _last_stdout(self) -> str:
        for action in reversed(self.actions):
            if action.get("ok") and str(action.get("stdout") or "").strip():
                return str(action.get("stdout"))
        return ""

    def _failure_text(self, claim: dict[str, Any]) -> str:
        if claim.get("missing_artifacts"):
            return (
                "claimed artifacts were not found in the workspace: "
                f"{claim['missing_artifacts']!r}"
            )
        if claim and str(claim.get("status") or "").lower() != "success":
            return str(claim.get("answer") or "step reported it could not finish")
        for action in reversed(self.actions):
            if not action.get("ok"):
                error = str(action.get("error") or action.get("stderr") or "").strip()
                if error:
                    return error.splitlines()[0][:400]
        return self._stop_reason or "step ended without a verified outcome"


def run_goal_step(request: StepRequest) -> dict[str, Any]:
    """Execute one plain-English goal and return its observable outcome."""
    return StepExecution(request).run()
