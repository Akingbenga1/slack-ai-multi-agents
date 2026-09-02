"""Executor Agent (Sprint 48). Sequential plan execution with tool calling.

Loads a persisted plan and runs steps one at a time in order. Before each
step, preconditions are checked against runtime context (attachments, etc.).
Advice and halt steps produce user-facing output; halt and failed
preconditions stop the run without executing later steps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.app.agent.base import Agent, AgentContext, AgentResult
from api.app.agent.llm import ChatModel, get_chat_model
from api.app.agent.plan_steps import (
    RUN_UVX_TOOL_NAME,
    STEP_TYPE_ADVICE,
    STEP_TYPE_HALT,
    STEP_TYPE_TOOL,
    ExecutionContext,
    check_preconditions,
    english_instruction,
    infer_step_type,
    is_english_goal_step,
    precondition_fail_message,
    step_message,
    step_meta,
    tool_arguments,
)
from api.app.agent.tools import (
    DbToolDiscovery,
    ToolDiscovery,
    ToolExecutionError,
    invoke_tool,
    is_unavailable_result,
    lookup_tool,
    result_error,
    tool_result_message,
)
from api.app.agent.tool_rag import load_full_tool_schema
from api.app.agent.llm import ToolSchema
from api.app.agent.uvx_runner import run_uvx_from_arguments
from api.app.agent.uvx_invoke import build_uvx_attempt_ledger
from api.app.db.models import AgentPlan, AgentPlanStep, AgentRun
from api.app.db.plan_store import (
    get_agent_plan,
    insert_agent_run,
    list_agent_plan_steps,
)
from api.app.agent.outcome_verifier import (
    capture_working_scope,
    combine_results_for_plan_check,
    criteria_text,
    delivering_attempts,
    verify_step_outcome,
)
from api.app.logging_config import get_logger, log_tool_rag_activity

logger = get_logger("api.agent.executor")

_EXECUTOR_SYSTEM = (
    "You are the execution agent composing the final user-facing answer. "
    "Given the user's question and evidence from completed steps, write a clear, "
    "accurate reply. Use only the provided evidence; do not invent facts. "
    "When steps created or referenced files, mention their paths. "
    "Keep the answer concise and actionable."
)

_REACT_UVX_SYSTEM = (
    "You are a general-purpose execution agent. You receive one plain-English goal "
    "at a time and must accomplish it using the tools available.\n\n"
    "Available tools:\n"
    "1) run_uvx — run a real PyPI CLI via uvx / uv tool run. You choose the package "
    "and command-line arguments from your knowledge. Set help_only=true to inspect "
    "a package CLI when unsure of flags.\n"
    "2) write_text_file — write UTF-8 text (plain text, HTML, CSV, JSON, Markdown, "
    "etc.) to a relative path under the working directory.\n"
    "3) write_pdf_text — write a simple text-only PDF under the working directory "
    "(for basic text PDFs; prefer run_uvx for merge, split, OCR, or rich PDF work).\n\n"
    "How to work:\n"
    "- Read the goal, success criteria, attachments, and any prior step results.\n"
    "- Use attachment local_path values exactly (forward slashes are fine on Windows).\n"
    "- Prefer run_uvx for conversions, merge/split/combine, OCR, table extraction, "
    "compression, archives, spreadsheets, images, audio, and other CLI-capable tasks.\n"
    "- PyPI install names often differ from console script names: set from_spec to the "
    "installable package and package to the executable (e.g. from_spec=pyexcel-cli, "
    "package=pyexcel). Never pass the install/package name as package when they differ.\n"
    "- Use with_packages for format plugins implied by input extensions (e.g. "
    "pyexcel-xlsx for .xlsx inputs).\n"
    "- Help probes: set help_only=true. Top-level CLI help uses empty args_list. "
    "Subcommand help uses help_path=['<subcommand>'] (or args_list=['<subcommand>'] "
    "with help_only=true). After top-level help lists a subcommand you need, run "
    "subcommand help before the real command.\n"
    "- If uvx reports an executable is not provided, fix package/from_spec — do not "
    "retry the same package name as the executable.\n"
    "- User question text may mention install names for motivation only; always follow "
    "the from_spec/package rules above for run_uvx.\n"
    "- Pick PyPI packages that expose a console script via uvx; pure libraries without "
    "executables cannot be run directly.\n"
    "- Write new outputs into the working directory with clear filenames. Never "
    "delete or overwrite the original attachments.\n"
    "- Multi-step plans: read prior step results before acting. If a step depends on "
    "earlier work and prior results lack a path, inspect the working directory before "
    "choosing tools or failing. Do not repeat work a prior step already finished.\n"
    "- If success criteria appear already met (expected output file exists), confirm "
    "and stop instead of running redundant tools.\n"
    "- After each tool result: read error_class, retryable, and suggested_next; "
    "retry with corrected args, run another tool, or stop when success criteria are met.\n"
    "- Informational goals (summarize, compare, explain): once you have enough "
    "content from tools, you may answer in plain text without further tool calls.\n"
    "- File-producing goals (merge, convert, export, create): you must create the "
    "output file via a tool — do not stop with prose alone.\n"
    "- Always use tools to make progress; do not reply with an empty message."
)

_RUN_UVX_SCHEMA = ToolSchema(
    name=RUN_UVX_TOOL_NAME,
    description=(
        "Install-and-run a PyPI console script via real uvx / uv tool run. "
        "Args: package (console script / executable name), optional from_spec "
        "(PyPI install spec when it differs from package), optional with_packages "
        "(extra deps as uvx --with), args_list (CLI argv after the entrypoint), "
        "optional help_path (subcommand names for help_only probes)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "package": {
                "type": "string",
                "description": "Console script to run (executable name), not the PyPI install name.",
            },
            "from_spec": {
                "type": "string",
                "description": "Optional uvx --from spec when install name differs, e.g. pyexcel-cli",
            },
            "with_packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional extra PyPI deps passed as repeated uvx --with flags.",
            },
            "args_list": {
                "type": "array",
                "items": {"type": "string"},
                "description": "CLI argv after the executable entrypoint.",
            },
            "help_path": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Subcommand path for help probes when help_only=true "
                    "(e.g. ['split'] runs `<exe> split --help`)."
                ),
            },
            "help_only": {"type": "boolean"},
        },
        "required": ["package"],
    },
)

_WRITE_FILE_SCHEMA = ToolSchema(
    name="write_text_file",
    description=(
        "Write UTF-8 text to a file under the working directory "
        "(relative path only; creates parent dirs)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
)

_WRITE_PDF_SCHEMA = ToolSchema(
    name="write_pdf_text",
    description=(
        "Write a simple text PDF into the working directory using local fpdf2. "
        "Args: path (relative filename), text (body), optional title."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "text": {"type": "string"},
            "title": {"type": "string"},
        },
        "required": ["path", "text"],
    },
)

def _uvx_max_attempts(extra: dict[str, Any]) -> int:
    settings = extra.get("settings")
    if settings is None:
        from api.app.settings import get_settings

        settings = get_settings()
    return max(1, int(getattr(settings, "executor_uvx_max_attempts", 8) or 8))


def _resolve_working_dir(context: AgentContext, arguments: dict[str, Any]) -> str | None:
    from pathlib import Path

    def _as_dir(raw: object) -> str | None:
        text = str(raw or "").strip()
        if not text:
            return None
        path = Path(text)
        if path.is_dir():
            return str(path.resolve())
        if path.is_file():
            return str(path.parent.resolve())
        # Not on disk yet — if it looks like a file, use parent
        if path.suffix:
            return str(path.parent.resolve()) if str(path.parent) not in {"", "."} else None
        return str(path.resolve())

    for key in ("cwd", "working_dir"):
        resolved = _as_dir(arguments.get(key))
        if resolved:
            return resolved
    # local_path on args/attachments is often a file; use its parent directory
    resolved = _as_dir(arguments.get("local_path"))
    if resolved:
        return resolved
    for att in context.attachments or []:
        if not isinstance(att, dict):
            continue
        for key in ("working_dir", "local_path", "path"):
            resolved = _as_dir(att.get(key))
            if resolved:
                return resolved
    return None


def _write_text_file(
    arguments: dict[str, Any],
    *,
    cwd: str | None,
) -> dict[str, Any]:
    """Write a relative UTF-8 text file under cwd (sandbox)."""
    from pathlib import Path

    rel = str(arguments.get("path") or "").strip().replace("\\", "/")
    content = arguments.get("content")
    if content is None:
        for key in ("text", "body", "html", "markdown", "data"):
            if arguments.get(key) is not None:
                content = arguments.get(key)
                break
    if (
        not rel
        or rel.startswith("/")
        or rel.startswith("~")
        or ".." in Path(rel).parts
    ):
        return {
            "ok": False,
            "error": "path must be a relative file under the working directory",
        }
    if content is None:
        return {"ok": False, "error": "content is required"}
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    target = (base / rel).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return {"ok": False, "error": "path escapes working directory"}
    target.parent.mkdir(parents=True, exist_ok=True)
    data = str(content)
    target.write_text(data, encoding="utf-8")
    return {
        "ok": True,
        "path": str(target),
        "output_file": str(target),
        "bytes_written": len(data.encode("utf-8")),
    }



def _write_pdf_text(
    arguments: dict[str, Any],
    *,
    cwd: str | None,
) -> dict[str, Any]:
    """Create a simple text PDF under cwd using project fpdf2."""
    from pathlib import Path

    from fpdf import FPDF

    rel = str(arguments.get("path") or "output.pdf").strip().replace(chr(92), "/")
    body = arguments.get("text")
    if body is None:
        body = arguments.get("content") or arguments.get("body") or ""
    title = str(arguments.get("title") or "Document Summary").strip() or "Document Summary"
    if (
        not rel
        or rel.startswith("/")
        or rel.startswith("~")
        or ".." in Path(rel).parts
    ):
        return {"ok": False, "error": "path must be a relative PDF under the working directory"}
    if not str(body).strip():
        return {"ok": False, "error": "text is required"}
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    target = (base / rel).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return {"ok": False, "error": "path escapes working directory"}
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, title)
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    safe = str(body).encode("latin-1", "replace").decode("latin-1")
    pdf.multi_cell(0, 6, safe)
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(target))
    return {
        "ok": True,
        "path": str(target),
        "output_file": str(target),
        "bytes_written": target.stat().st_size,
    }


def _execute_run_uvx_call(
    arguments: dict[str, Any],
    *,
    context: AgentContext,
    extra: dict[str, Any],
    db: Session,
    prior_attempts: list[dict[str, Any]] | None = None,
    instruction: str = "",
    success_criteria: str = "",
) -> dict[str, Any]:
    """Prefer injected test tool; otherwise call real uvx_runner with recovery."""
    args = dict(arguments or {})
    cwd = _resolve_working_dir(context, args)
    if cwd and "cwd" not in args:
        args["cwd"] = cwd
    injected = lookup_tool(
        RUN_UVX_TOOL_NAME, client_id=context.client_id, db=db, extra=extra
    )
    if injected is not None and injected.source == "injected" and injected.invoke:
        return invoke_tool(
            injected, args, client_id=context.client_id, db=db, extra=extra
        )
    return run_uvx_from_arguments(
        args,
        prior_attempts=prior_attempts,
        attachments=list(context.attachments or []),
        instruction=instruction,
        success_criteria=success_criteria,
    )


def _summarize_step_result(val: dict[str, Any]) -> str:
    """Compact, tool-agnostic summary of one prior step result."""
    parts: list[str] = []
    if val.get("ok") is True:
        parts.append("status: succeeded")
    elif val.get("ok") is False:
        err = str(val.get("error") or "failed").strip()
        parts.append(f"status: failed ({err})")

    for key in ("output_file", "path", "done_text"):
        text = str(val.get(key) or "").strip()
        if text:
            parts.append(f"{key}: {text}")

    attempts = val.get("attempts")
    if isinstance(attempts, list) and not any(
        p.startswith(("output_file:", "path:")) for p in parts
    ):
        for attempt in reversed(attempts):
            if not isinstance(attempt, dict) or not attempt.get("ok"):
                continue
            artifact = str(
                attempt.get("output_file") or attempt.get("path") or ""
            ).strip()
            if artifact:
                parts.append(f"output_file: {artifact}")
                break

    stdout = str(val.get("stdout") or "").strip()
    if stdout:
        parts.append(f"stdout:\n{stdout[:2000]}")

    return "\n".join(parts)


def _format_prior_step_results(prior: dict[str, Any] | None) -> str:
    if not isinstance(prior, dict) or not prior:
        return "(none)"
    chunks: list[str] = []
    for key, val in list(prior.items())[:8]:
        if isinstance(val, dict):
            snippet = _summarize_step_result(val)
        else:
            snippet = str(val)[:1000]
        if snippet.strip():
            chunks.append(f"[{key}]\n{snippet}")
    return "\n\n".join(chunks) if chunks else "(none)"


def _format_uvx_observation(attempt: dict[str, Any]) -> str:
    notes: list[str] = []
    if attempt.get("preflight_corrected"):
        notes.append(f"preflight_notes={attempt.get('preflight_notes')!r}")
    if attempt.get("remediated"):
        notes.append("remediated=true")
    if attempt.get("help_ladder"):
        notes.append("help_ladder=true")
    if attempt.get("code") == "duplicate_attempt":
        notes.append("duplicate_attempt_blocked=true")
    header = " ".join(notes)
    structured = (
        f"error_class={attempt.get('error_class')!r} "
        f"retryable={attempt.get('retryable')!r}\n"
        f"suggested_next={attempt.get('suggested_next')!r}\n"
    )
    return (
        structured
        + f"uvx package={attempt.get('package')!r} "
        f"from_spec={attempt.get('from_spec')!r} "
        f"with_packages={attempt.get('with_packages')!r} "
        f"exit={attempt.get('exit_code')!r} ok={attempt.get('ok')!r}"
        f"{(' ' + header) if header else ''}\n"
        f"output_files={attempt.get('output_files')!r}\n"
        f"stdout:\n{(attempt.get('stdout') or '')[:4000]}\n"
        f"stderr:\n"
        f"{(attempt.get('stderr') or attempt.get('error') or '')[:1000]}"
    )


def _append_uvx_attempts(
    attempts: list[dict[str, Any]],
    result: dict[str, Any],
    *,
    round_i: int,
    call_args: dict[str, Any],
) -> list[dict[str, Any]]:
    """Flatten primary + help-ladder attempts into the step attempt log."""
    batch: list[dict[str, Any]] = []
    primary = {
        **result,
        "round": round_i + 1,
        "tool": RUN_UVX_TOOL_NAME,
        "help_only": bool(call_args.get("help_only") or call_args.get("help")),
        "args_list": list(call_args.get("args_list") or []),
        "from_spec": call_args.get("from_spec") or call_args.get("from"),
        "with_packages": call_args.get("with_packages") or call_args.get("with"),
    }
    batch.append(primary)
    for ladder in result.get("ladder_attempts") or []:
        if isinstance(ladder, dict):
            batch.append(
                {
                    **ladder,
                    "round": round_i + 1,
                    "tool": RUN_UVX_TOOL_NAME,
                    "help_only": True,
                }
            )
    attempts.extend(batch)
    return batch


def _build_react_user_prompt(
    *,
    context: AgentContext,
    instruction: str,
    success_criteria: str | None,
    cwd: str | None,
    attachment_block: str,
    prior_block: str,
) -> str:
    return "\n".join(
        [
            f"User intent: {context.question or ''}",
            "Note: package or tool names mentioned in the user intent are hints only; "
            "follow system rules for run_uvx from_spec/package/with_packages.",
            f"Goal: {instruction}",
            f"Success criteria: {success_criteria or '(meet the goal)'}",
            f"Working directory: {cwd or '(default)'}",
            "Attachments (use exact local_path; forward slashes are fine):",
            attachment_block,
            "Prior step results (reuse when possible):",
            prior_block,
        ]
    )


def _react_success_from_attempts(
    attempts: list[dict[str, Any]],
    *,
    instruction: str,
    done_text: str = "",
) -> dict[str, Any] | None:
    """Return a success payload when delivering attempts exist (not probes)."""
    productive = delivering_attempts(attempts)
    if not productive:
        return None
    last_ok = productive[-1]
    payload = {
        **last_ok,
        "attempt_count": len(attempts),
        "attempts": attempts,
        "instruction": instruction,
    }
    if done_text:
        payload["done_text"] = done_text
    output = last_ok.get("output_file") or last_ok.get("path")
    if output:
        payload["output_file"] = output
    return payload


def _run_english_goal_react(
    *,
    context: AgentContext,
    extra: dict[str, Any],
    db: Session,
    instruction: str,
    success_criteria: str | None,
    step_arguments: dict[str, Any],
) -> dict[str, Any]:
    """ReAct loop: LLM chooses package/args; real uvx executes."""
    max_attempts = _uvx_max_attempts(extra)
    attempts: list[dict[str, Any]] = []
    cwd = _resolve_working_dir(context, step_arguments)
    attachment_lines: list[str] = []
    for att in context.attachments or []:
        if not isinstance(att, dict):
            continue
        name = att.get("filename") or ""
        local = att.get("local_path") or ""
        if local:
            local = str(local).replace("\\", "/")
        if name or local:
            attachment_lines.append(f"- filename={name!r} local_path={local!r}")
    attachment_block = "\n".join(attachment_lines) if attachment_lines else "(none)"

    prior_block = _format_prior_step_results(step_arguments.get("prior_step_results"))

    user = _build_react_user_prompt(
        context=context,
        instruction=instruction,
        success_criteria=success_criteria,
        cwd=cwd,
        attachment_block=attachment_block,
        prior_block=prior_block,
    )
    messages: list[dict[str, str]] = [{"role": "user", "content": user}]
    model = _chat_model(extra)
    last_result: dict[str, Any] = {
        "ok": False,
        "error": "no uvx attempts",
        "attempt_count": 0,
        "attempts": [],
        "instruction": instruction,
    }

    for round_i in range(max_attempts):
        round_messages = list(messages)
        ledger = build_uvx_attempt_ledger(attempts, max_attempts=max_attempts)
        if ledger:
            round_messages = [{"role": "user", "content": ledger}, *round_messages]
        llm = model.complete(
            system=_REACT_UVX_SYSTEM,
            messages=round_messages,
            model_tier="fast",
            tools=[_RUN_UVX_SCHEMA, _WRITE_FILE_SCHEMA, _WRITE_PDF_SCHEMA],
        )
        if not llm.has_tool_calls:
            done_text = (llm.text or "").strip()
            success = _react_success_from_attempts(
                attempts, instruction=instruction, done_text=done_text
            )
            if success is not None:
                return success
            if round_i < max_attempts - 1:
                messages.append(
                    {
                        "role": "assistant",
                        "content": done_text or "(no tool call yet)",
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You must make progress using run_uvx, write_text_file, "
                            "or write_pdf_text. Choose an appropriate PyPI package "
                            "and call run_uvx now, or write the required output file."
                        ),
                    }
                )
                continue
            last_result = {
                "ok": False,
                "error": done_text or "executor stopped without success",
                "attempt_count": len(attempts),
                "attempts": attempts,
                "instruction": instruction,
            }
            break

        for call in llm.tool_calls:
            call_name = (call.name or "").strip()
            call_args = dict(call.arguments or {})
            if call_name == "write_pdf_text":
                result = _write_pdf_text(call_args, cwd=cwd)
                attempt = {**result, "round": round_i + 1, "tool": call_name}
                attempts.append(attempt)
                last_result = {
                    **attempt,
                    "attempt_count": len(attempts),
                    "attempts": attempts,
                    "instruction": instruction,
                }
                obs = (
                    f"write_pdf_text ok={attempt.get('ok')!r} "
                    f"path={attempt.get('path')!r} "
                    f"error={attempt.get('error')!r}"
                )
                messages.append({"role": "user", "content": f"Tool result:\n{obs}"})
                if attempt.get("ok") is True:
                    return {
                        **attempt,
                        "attempt_count": len(attempts),
                        "attempts": attempts,
                        "instruction": instruction,
                        "output_file": attempt.get("output_file") or attempt.get("path"),
                    }
                continue
            if call_name == "write_text_file":
                result = _write_text_file(call_args, cwd=cwd)
                attempt = {**result, "round": round_i + 1, "tool": call_name}
                attempts.append(attempt)
                last_result = {
                    **attempt,
                    "attempt_count": len(attempts),
                    "attempts": attempts,
                    "instruction": instruction,
                }
                obs = (
                    f"write_text_file ok={attempt.get('ok')!r} "
                    f"path={attempt.get('path')!r} "
                    f"error={attempt.get('error')!r}"
                )
                messages.append({"role": "user", "content": f"Tool result:\n{obs}"})
                continue
            if call_name != RUN_UVX_TOOL_NAME:
                attempts.append(
                    {
                        "ok": False,
                        "error": f"unsupported tool call: {call.name}",
                        "package": None,
                        "tool": call_name,
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Tool result ERROR: only run_uvx, write_text_file, and "
                            "write_pdf_text are allowed. Try again."
                        ),
                    }
                )
                continue
            if cwd and "cwd" not in call_args:
                call_args["cwd"] = cwd
            result = _execute_run_uvx_call(
                call_args,
                context=context,
                extra=extra,
                db=db,
                prior_attempts=attempts,
                instruction=instruction,
                success_criteria=success_criteria or "",
            )
            batch = _append_uvx_attempts(
                attempts,
                result if isinstance(result, dict) else {"ok": False, "error": str(result)},
                round_i=round_i,
                call_args=call_args,
            )
            last_result = {
                **batch[-1],
                "attempt_count": len(attempts),
                "attempts": attempts,
                "instruction": instruction,
            }
            obs_parts = [_format_uvx_observation(item) for item in batch]
            messages.append(
                {
                    "role": "user",
                    "content": "Tool result:\n" + "\n\n".join(obs_parts),
                }
            )

    if delivering_attempts(attempts):
        success = _react_success_from_attempts(attempts, instruction=instruction)
        if success is not None:
            return success
    last_result["attempt_count"] = len(attempts)
    last_result["attempts"] = attempts
    if not last_result.get("error"):
        last_result["error"] = "uvx attempts exhausted without success"
    return last_result


def _chat_model(extra: dict[str, Any]) -> ChatModel:
    model = extra.get("chat_model")
    if model is not None:
        return model
    force_stub = bool(extra.get("force_stub"))
    return get_chat_model(force_stub=force_stub)


def _compose_final_answer(
    *,
    context: AgentContext,
    extra: dict[str, Any],
    evidence_lines: list[str],
    fallback: str,
) -> str:
    """LLM final answer from tool results; falls back to joined tool text."""
    evidence = "\n\n".join(line for line in evidence_lines if line).strip()
    if not evidence and not (context.question or "").strip():
        return fallback
    user = (
        f"Question: {context.question or ''}\n\n"
        f"Tool results:\n{evidence or '(none)'}"
    )
    try:
        result = _chat_model(extra).complete(
            system=_EXECUTOR_SYSTEM,
            messages=[{"role": "user", "content": user}],
            model_tier="fast",
        )
    except Exception:
        logger.exception(
            "executor_compose_failed client_id=%s", context.client_id
        )
        return fallback
    text = (result.text or "").strip()
    if not text or text in {
        "All steps completed.",
        "All done.",
        "done",
        "Done.",
    }:
        return fallback
    return text


def _session(extra: dict[str, Any]) -> tuple[Session, bool]:
    db = extra.get("db")
    if db is not None:
        return db, False
    factory = extra.get("db_factory")
    if callable(factory):
        return factory(), True
    from api.app.db.session import SessionLocal

    return SessionLocal(), True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _finish_run(
    plan: AgentPlan,
    run: AgentRun,
    *,
    status: str,
    error: str | None,
) -> None:
    plan.status = status
    run.status = status
    run.error = error
    run.finished_at = _now()


def _halt_step(
    step: AgentPlanStep,
    *,
    result_key: str,
    message: str,
) -> None:
    step.status = "succeeded"
    step.result = {result_key: message}
    step.error = None


def _skip_remaining(steps: list[AgentPlanStep], start_index: int) -> None:
    for pending in steps[start_index + 1 :]:
        if pending.status == "pending":
            pending.status = "skipped"


def _log_step_boundary(
    *,
    phase: str,
    context: AgentContext,
    plan_id: str,
    step_index: int,
    tool_name: str,
    scope_dir: str | None,
) -> None:
    snapshot = capture_working_scope(scope_dir)
    log_tool_rag_activity(
        phase="executor_step_boundary",
        client_id=context.client_id,
        boundary_phase=phase,
        plan_id=plan_id,
        step_index=step_index,
        tool_name=tool_name,
        working_scope=snapshot,
    )


def _final_goal_step(steps: list[AgentPlanStep]) -> AgentPlanStep | None:
    for step in reversed(steps):
        meta = step_meta(step.arguments)
        step_type = infer_step_type(step.tool_name or "", meta)
        if step_type in (STEP_TYPE_ADVICE, STEP_TYPE_HALT):
            continue
        if (step.tool_name or "").strip():
            return step
    return None


def _plan_goal_verification(
    *,
    steps: list[AgentPlanStep],
    step_results: dict[str, Any],
    current_result: dict[str, Any],
    context: AgentContext,
    invoke_args: dict[str, Any],
):
    final = _final_goal_step(steps)
    if final is None:
        return None
    criteria = criteria_text(final.success_criteria)
    if not criteria:
        return None
    merged = combine_results_for_plan_check(step_results)
    for key in ("output_file", "path", "stdout", "done_text", "attempts"):
        if current_result.get(key) and not merged.get(key):
            merged[key] = current_result.get(key)
    if current_result.get("ok"):
        merged["ok"] = True
    instruction = english_instruction(tool_arguments(final.arguments)) or criteria
    cwd = _resolve_working_dir(context, invoke_args)
    return verify_step_outcome(
        success_criteria=criteria,
        instruction=instruction,
        result=merged,
        scope_dir=cwd,
    )


class ExecutorAgent(Agent):
    """Sequential executor. Runs plan steps in order with precondition gates."""

    @property
    def role(self) -> str:
        return "executor"

    def _run_impl(self, context: AgentContext) -> AgentResult:
        extra = dict(context.extra or {})
        plan_id = extra.get("plan_id")
        if not plan_id:
            return AgentResult(
                role=self.role,
                client_id=context.client_id,
                status="failed",
                message="plan_id is required",
            )
        db, own_session = _session(extra)
        try:
            return self._execute(context, db, extra, plan_id)
        finally:
            if own_session:
                db.close()

    def _execute(
        self,
        context: AgentContext,
        db: Session,
        extra: dict[str, Any],
        plan_id: Any,
    ) -> AgentResult:
        plan = get_agent_plan(
            db, tenant_id=context.client_id, plan_id=plan_id
        )
        if plan is None:
            return AgentResult(
                role=self.role,
                client_id=context.client_id,
                status="failed",
                message="plan not found for this tenant",
                extra={"plan_id": str(plan_id)},
            )

        run = insert_agent_run(
            db,
            tenant_id=context.client_id,
            plan_id=plan.id,
            status="running",
        )
        run.started_at = _now()
        plan.status = "running"
        db.flush()

        steps = list_agent_plan_steps(
            db, tenant_id=context.client_id, plan_id=plan.id
        )
        exec_ctx = ExecutionContext.from_agent_context(
            client_id=context.client_id,
            attachments=context.attachments,
            plan_source=plan.source if isinstance(plan.source, dict) else None,
        )
        discovery = DbToolDiscovery(db, extra)

        output_lines: list[str] = []
        step_results: dict[str, Any] = {}
        for index, step in enumerate(steps):
            meta = step_meta(step.arguments)
            step_type = infer_step_type(step.tool_name or "", meta)
            tool_name = (step.tool_name or "").strip()

            ok, reason = check_preconditions(
                meta.get("preconditions") or {}, exec_ctx
            )
            if not ok:
                message = precondition_fail_message(meta, reason)
                step.status = "skipped"
                step.error = reason
                step.result = {"precondition_failed": message}
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="succeeded", error=None)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="succeeded",
                    message=message,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            if step_type == STEP_TYPE_HALT:
                message = step_message(step.arguments) or "execution halted"
                _halt_step(step, result_key="halt", message=message)
                output_lines.append(message)
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="succeeded", error=None)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="succeeded",
                    message=message,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            if step_type == STEP_TYPE_ADVICE:
                message = step_message(step.arguments)
                _halt_step(step, result_key="advice", message=message)
                if message:
                    output_lines.append(message)
                if meta.get("stop_after"):
                    _skip_remaining(steps, index)
                    final = "\n\n".join(output_lines).strip() or "plan executed"
                    _finish_run(plan, run, status="succeeded", error=None)
                    db.commit()
                    return AgentResult(
                        role=self.role,
                        client_id=context.client_id,
                        status="succeeded",
                        message=final,
                        extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                    )
                db.flush()
                continue

            if step_type != STEP_TYPE_TOOL:
                step.status = "failed"
                step.error = f"unknown step type: {step_type}"
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="failed", error=step.error)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="failed",
                    message=step.error,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            if not tool_name:
                step.status = "failed"
                step.error = "empty tool_name"
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="failed", error=step.error)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="failed",
                    message=step.error,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            step.status = "running"
            db.flush()
            invoke_args = tool_arguments(step.arguments)
            if step_results:
                invoke_args = {
                    **invoke_args,
                    "prior_step_results": dict(step_results),
                }
            step_cwd = _resolve_working_dir(context, invoke_args)
            _log_step_boundary(
                phase="start",
                context=context,
                plan_id=str(plan.id),
                step_index=index,
                tool_name=tool_name,
                scope_dir=step_cwd,
            )
            step_criteria = criteria_text(step.success_criteria)

            try:
                if is_english_goal_step(tool_name, invoke_args):
                    instruction = english_instruction(invoke_args) or (
                        step_criteria or tool_name
                    )
                    log_tool_rag_activity(
                        phase="executor_english_goal",
                        client_id=context.client_id,
                        plan_id=str(plan.id),
                        step_index=index,
                        tool_name=tool_name,
                        instruction=instruction[:200],
                    )
                    result = _run_english_goal_react(
                        context=context,
                        extra=extra,
                        db=db,
                        instruction=instruction,
                        success_criteria=step_criteria or None,
                        step_arguments=invoke_args,
                    )
                elif tool_name == RUN_UVX_TOOL_NAME:
                    log_tool_rag_activity(
                        phase="executor_run_uvx",
                        client_id=context.client_id,
                        plan_id=str(plan.id),
                        step_index=index,
                        tool_name=tool_name,
                    )
                    result = _execute_run_uvx_call(
                        invoke_args, context=context, extra=extra, db=db
                    )
                    if isinstance(result, dict):
                        result.setdefault("attempt_count", 1)
                else:
                    ref = discovery.find(tool_name, client_id=context.client_id)
                    if ref is None:
                        error_msg = f"tool not found: {tool_name}"
                        step.status = "failed"
                        step.error = error_msg
                        _skip_remaining(steps, index)
                        _finish_run(plan, run, status="failed", error=error_msg)
                        db.commit()
                        return AgentResult(
                            role=self.role,
                            client_id=context.client_id,
                            status="failed",
                            message=error_msg,
                            extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                        )

                    # Lazy-load full schema/config only after the tool is chosen.
                    full_schema = load_full_tool_schema(ref)
                    log_tool_rag_activity(
                        phase="executor_resolve",
                        client_id=context.client_id,
                        plan_id=str(plan.id),
                        step_index=index,
                        tool_name=ref.name,
                        kind=ref.kind,
                        source=ref.source,
                        has_subcommands=bool(full_schema.get("subcommands")),
                    )
                    result = invoke_tool(
                        ref,
                        invoke_args,
                        client_id=context.client_id,
                        db=db,
                        extra=extra,
                    )
            except ToolExecutionError as exc:
                error_msg = str(exc)
                step.status = "failed"
                step.error = error_msg
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="failed", error=error_msg)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="failed",
                    message=error_msg,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            if is_unavailable_result(result):
                note = tool_result_message(tool_name, result)
                step.status = "skipped"
                step.error = note
                step.result = result
                output_lines.append(note)
                db.flush()
                continue

            instruction_for_verify = None
            if is_english_goal_step(tool_name, invoke_args):
                instruction_for_verify = (
                    english_instruction(invoke_args) or step_criteria or tool_name
                )

            _log_step_boundary(
                phase="end",
                context=context,
                plan_id=str(plan.id),
                step_index=index,
                tool_name=tool_name,
                scope_dir=step_cwd,
            )

            if isinstance(result, dict) and (
                is_english_goal_step(tool_name, invoke_args) or step_criteria
            ):
                verification = verify_step_outcome(
                    success_criteria=step.success_criteria,
                    instruction=instruction_for_verify,
                    result=result,
                    scope_dir=step_cwd,
                )
                result = {
                    **result,
                    "verification_method": verification.method,
                    "verification_reason": verification.reason,
                }
                if verification.verified and not result.get("ok"):
                    result["ok"] = True
                    result["verified"] = True
                elif result.get("ok") and not verification.verified:
                    result["ok"] = False
                    result["error"] = verification.reason

            failed = result_error(result)
            if failed:
                plan_check = _plan_goal_verification(
                    steps=steps,
                    step_results=step_results,
                    current_result=result if isinstance(result, dict) else {},
                    context=context,
                    invoke_args=invoke_args,
                )
                if plan_check is not None and plan_check.verified:
                    step.status = "skipped"
                    step.error = failed
                    step.result = {
                        **(result if isinstance(result, dict) else {"error": failed}),
                        "plan_level_success": True,
                        "verification_method": plan_check.method,
                        "verification_reason": plan_check.reason,
                    }
                    _skip_remaining(steps, index)
                    final_message = "\n\n".join(output_lines).strip() or plan_check.reason
                    if output_lines:
                        final_message = _compose_final_answer(
                            context=context,
                            extra=extra,
                            evidence_lines=output_lines,
                            fallback=final_message,
                        )
                    _finish_run(plan, run, status="succeeded", error=None)
                    db.commit()
                    return AgentResult(
                        role=self.role,
                        client_id=context.client_id,
                        status="succeeded",
                        message=final_message,
                        extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                    )
                step.status = "failed"
                step.error = failed
                step.result = result
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="failed", error=failed)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="failed",
                    message=failed,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            step.status = "succeeded"
            step.result = result
            step.error = None
            step_results[tool_name] = result
            step_results[f"step_{index}"] = result
            text = tool_result_message(tool_name, result)
            if text:
                output_lines.append(text)
            db.flush()

        final_message = "\n\n".join(output_lines).strip() or "plan executed"
        if output_lines:
            final_message = _compose_final_answer(
                context=context,
                extra=extra,
                evidence_lines=output_lines,
                fallback=final_message,
            )
        _finish_run(plan, run, status="succeeded", error=None)
        db.commit()
        return AgentResult(
            role=self.role,
            client_id=context.client_id,
            status="succeeded",
            message=final_message,
            extra={"plan_id": str(plan.id), "run_id": str(run.id)},
        )
