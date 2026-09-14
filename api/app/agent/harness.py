"""Deep Agents harness adapter for tenant dry-run / plan-and-execute entry.

Product entry for tenant office work: tenant-scoped workspace, staged inputs,
promoted outputs, and outcome verification against observable artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from api.app.agent.base import AgentResult
from api.app.agent.guardrails import require_tenant_client_id
from api.app.agent.llm_config import (
    ADAPTER_SHAPE_ANTHROPIC,
    ADAPTER_SHAPE_OPENAI_COMPAT,
    ADAPTER_SHAPE_STUB,
    resolve_llm_runtime_config,
)
from api.app.agent.outcome_verifier import VerificationResult, verify_step_outcome
from api.app.agent.workspace import (
    RunWorkspace,
    create_run_workspace,
    promote_outputs,
)
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.harness")

_SYSTEM_PROMPT = """You are an office-document agent. Complete the user's request \
using the files in this workspace.

Rules:
- Work only inside the current workspace directory.
- Prefer creating new output files; do not delete or replace the user's originals.
- When transforming an attached file, write a new artifact and leave inputs intact.
- Use shell/python tools when needed (uvx, python, LibreOffice, etc.).
- Tenant skills may be available via list_tenant_skills and load_tenant_skill. \
First list the short index (name + description); load the full markdown only for \
the one skill you need (progressive disclosure). If the user names a skill, load that.
- Tenant MCP tools (names starting with mcp__) may be available; after seeing the \
tool list, call only the MCP tools necessary for this request — not every tool.
- MCP tools are available when relevant, not required for every request.
- Verify the outcome yourself (open the file, check pages/text) before finishing.
- When done, reply with a short plain-language summary of what was produced \
and where it lives (relative workspace paths).
"""


def _settings(extra: dict[str, Any]) -> Settings:
    settings = extra.get("settings")
    if isinstance(settings, Settings):
        return settings
    return get_settings()


def _resolve_model(settings: Settings) -> Any:
    """Build a Deep Agents-compatible model from role-named settings."""
    config = resolve_llm_runtime_config(settings)
    if config.adapter_shape == ADAPTER_SHAPE_STUB:
        raise ValueError(
            "LLM_PROVIDER=stub cannot drive the Deep Agents harness; "
            "inject harness_agent or set a real provider"
        )
    if config.adapter_shape == ADAPTER_SHAPE_ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        model_id = (config.model_capable or "").strip()
        if not model_id:
            model_id = "claude-sonnet-4-20250514"
        # Pass the key from Settings explicitly: pydantic loads .env into
        # Settings, but that does not always export ANTHROPIC_API_KEY to the
        # process environment that LangChain string models expect.
        return ChatAnthropic(
            model_name=model_id,
            api_key=config.api_key,
            max_tokens=max(config.max_tokens, 8192),
        )
    if config.adapter_shape == ADAPTER_SHAPE_OPENAI_COMPAT:
        from langchain.chat_models import init_chat_model

        model_id = (config.model_capable or "").strip() or "llama3.1"
        base = (config.base_url or "").strip().rstrip("/")
        kwargs: dict[str, Any] = {"model": model_id, "model_provider": "openai"}
        if base:
            if not base.endswith("/v1"):
                base = base + "/v1"
            kwargs["base_url"] = base
        kwargs["api_key"] = (config.api_key or "").strip() or "not-needed"
        return init_chat_model(**kwargs)
    raise ValueError(
        f"unsupported adapter shape {config.adapter_shape!r} for Deep Agents"
    )


def _build_user_message(
    question: str,
    workspace: RunWorkspace,
) -> str:
    parts = [f"User request:\n{question.strip()}"]
    if workspace.inputs:
        listing = [
            {
                "filename": item.name,
                "workspace_path": item.relative_path,
                "bytes": item.size_bytes,
            }
            for item in workspace.inputs
        ]
        parts.append(
            "Staged attachments in the workspace "
            "(read these; write new outputs beside them):\n"
            + json.dumps(listing, indent=2)
        )
    parts.append(
        "Complete the request. Leave staged inputs unchanged. "
        "Create new files for any deliverable."
    )
    return "\n\n".join(parts)


def _message_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        bits: list[str] = []
        for part in content:
            if isinstance(part, str):
                bits.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                bits.append(str(part.get("text") or ""))
            else:
                text = getattr(part, "text", None)
                if text:
                    bits.append(str(text))
        return "\n".join(bits).strip()
    return str(content).strip()


def _final_assistant_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload or "").strip()
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return _message_text(payload.get("output")) or ""
    for msg in reversed(messages):
        role = getattr(msg, "type", None) or getattr(msg, "role", None)
        if isinstance(msg, dict):
            role = msg.get("type") or msg.get("role")
            content = msg.get("content")
        else:
            content = getattr(msg, "content", "")
        role_text = str(role or "").lower()
        if role_text in {"ai", "assistant"}:
            text = _message_text(content)
            if text:
                return text
    last = messages[-1]
    if isinstance(last, dict):
        return _message_text(last.get("content"))
    return _message_text(getattr(last, "content", ""))


def _trace_messages(payload: Any, *, limit: int = 40) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return []
    out: list[dict[str, Any]] = []
    for msg in messages[-limit:]:
        if isinstance(msg, dict):
            role = str(msg.get("type") or msg.get("role") or "")
            content = _message_text(msg.get("content"))
            tool_calls = msg.get("tool_calls")
        else:
            role = str(getattr(msg, "type", None) or getattr(msg, "role", "") or "")
            content = _message_text(getattr(msg, "content", ""))
            tool_calls = getattr(msg, "tool_calls", None)
        entry: dict[str, Any] = {"role": role, "content": content[:4000]}
        if tool_calls:
            entry["tool_calls"] = tool_calls
        out.append(entry)
    return out


def _delivery_destination(attachments: list[dict[str, Any]]) -> Path | None:
    for att in attachments:
        if not isinstance(att, dict):
            continue
        for key in ("local_path", "path"):
            raw = str(att.get(key) or "").strip()
            if not raw:
                continue
            parent = Path(raw).parent
            if parent.is_dir():
                return parent.resolve()
    return None


def _known_input_paths(workspace: RunWorkspace) -> list[Path]:
    paths: list[Path] = []
    for item in workspace.inputs:
        staged = workspace.root / item.relative_path
        if staged.is_file():
            paths.append(staged.resolve())
        source = Path(item.source_path)
        if source.is_file():
            paths.append(source.resolve())
    return paths


def _create_agent(
    *,
    model: Any,
    workspace: RunWorkspace,
    settings: Settings,
    tools: list[Any] | None = None,
) -> Any:
    from deepagents import create_deep_agent
    from deepagents.backends import LocalShellBackend

    root = str(workspace.root.resolve())
    # Local shell is the Deep Agents-supported execute backend for local runs.
    # Deep Agents rejects filesystem `permissions=` when the backend exposes
    # `execute` (SandboxBackendProtocol); isolation is the workspace root plus
    # staged copies / promote / verify instead. Multi-tenant production should
    # later swap to an isolated sandbox backend.
    backend = LocalShellBackend(
        root_dir=root,
        virtual_mode=True,
        timeout=int(getattr(settings, "cli_tools_timeout_seconds", 120) or 120),
        inherit_env=True,
    )
    return create_deep_agent(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        backend=backend,
        tools=list(tools or []),
        name="tenant-office-harness",
    )


def run_deep_agent(
    *,
    client_id: str,
    question: str,
    conversation_id: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> AgentResult:
    """Run one Deep Agents session for the tenant and return an AgentResult."""
    extra = dict(extra or {})
    cid = require_tenant_client_id(client_id, where="agent.harness")
    settings = _settings(extra)
    include_trace = bool(extra.get("include_trace"))
    attachments = list(attachments or [])
    run_key = str(extra.get("run_key") or conversation_id or uuid4())

    injected_runner: Callable[..., AgentResult] | None = extra.get("harness_runner")
    if callable(injected_runner):
        return injected_runner(
            client_id=cid,
            question=question,
            conversation_id=conversation_id,
            attachments=attachments,
            extra=extra,
        )

    workspace = create_run_workspace(
        client_id=cid,
        run_key=run_key,
        attachments=attachments,
        settings=settings,
    )
    user_message = _build_user_message(question, workspace)
    logger.info(
        "harness_start client_id=%s run_key=%s inputs=%s",
        cid,
        run_key,
        len(workspace.inputs),
    )

    mcp_runtime = None
    mcp_tools: list[Any] = []
    try:
        from api.app.agent.tenant_mcp import build_tenant_mcp_runtime
        from api.app.db.session import SessionLocal

        db = SessionLocal()
        try:
            mcp_runtime = build_tenant_mcp_runtime(
                db, tenant_id=cid, run_key=run_key, settings=settings
            )
            mcp_tools = list(mcp_runtime.tools)
        finally:
            db.close()
    except Exception:
        logger.exception("tenant_mcp_runtime_failed client_id=%s", cid)

    skill_runtime = None
    skill_tools: list[Any] = []
    try:
        from api.app.skills.provider import build_tenant_skill_runtime

        injected_provider = extra.get("skill_provider")
        skill_runtime = build_tenant_skill_runtime(
            client_id=cid,
            run_key=run_key,
            settings=settings,
            blob_store=extra.get("blob_store"),
            provider=injected_provider if injected_provider is not None else None,
        )
        skill_tools = list(skill_runtime.tools)
    except Exception:
        logger.exception("tenant_skill_runtime_failed client_id=%s", cid)

    agent = extra.get("harness_agent")
    invoke_error: str | None = None
    raw_result: Any = None
    try:
        if agent is None:
            model = extra.get("harness_model") or _resolve_model(settings)
            agent = _create_agent(
                model=model,
                workspace=workspace,
                settings=settings,
                tools=[*mcp_tools, *skill_tools],
            )
        raw_result = agent.invoke(
            {"messages": [{"role": "user", "content": user_message}]}
        )
    except Exception as exc:
        logger.exception("harness_invoke_failed client_id=%s", cid)
        invoke_error = str(exc)

    answer = _final_assistant_text(raw_result) if raw_result is not None else ""
    if invoke_error and not answer:
        answer = f"Harness run failed: {invoke_error}"

    destination = _delivery_destination(attachments)
    delivered: list[str] = []
    if destination is not None:
        try:
            delivered = promote_outputs(workspace, destination=destination)
        except OSError:
            logger.exception("harness_promote_failed client_id=%s", cid)

    known_inputs = _known_input_paths(workspace)
    produced_paths = [Path(p) for p in delivered if Path(p).is_file()]
    if not produced_paths:
        input_names = {item.relative_path for item in workspace.inputs}
        for path in workspace.root.rglob("*"):
            if not path.is_file() or workspace.is_internal(path):
                continue
            rel = workspace.relative_of(path)
            if rel in input_names:
                continue
            produced_paths.append(path.resolve())

    verification = verify_step_outcome(
        success_criteria=question,
        instruction=question,
        result={
            "ok": not invoke_error,
            "output_files": [str(p) for p in produced_paths],
            "done_text": answer,
        },
        scope_dir=workspace.root,
        known_inputs=known_inputs,
    )
    if invoke_error:
        status = "failed"
        verification = VerificationResult(
            False,
            invoke_error,
            "harness_error",
            paths=tuple(str(p) for p in produced_paths),
        )
    elif verification.verified:
        status = "succeeded"
    elif produced_paths:
        status = "partial"
    else:
        status = "failed"

    if delivered and status != "succeeded":
        note = "Files produced before the run stopped:\n" + "\n".join(delivered)
        answer = f"{answer}\n\n{note}".strip() if answer else note

    result_extra: dict[str, Any] = {
        "plan_id": run_key,
        "run_id": run_key,
        "phase": "harness",
        "workflow": "deep_agents",
        "delivered_files": list(delivered),
        "workspace_root": str(workspace.root),
        "step_diagnostics": [
            {
                "step_index": 0,
                "tool_name": "deep_agents",
                "status": status,
                "verification_method": verification.method,
                "verification_reason": verification.reason,
                "outcome": status,
            }
        ],
    }
    if mcp_runtime is not None:
        from api.app.agent.tenant_mcp import usage_as_dicts

        result_extra["mcp_servers"] = list(mcp_runtime.server_summaries)
        result_extra["mcp_usage"] = usage_as_dicts(mcp_runtime.usage)
    if skill_runtime is not None:
        from api.app.skills.provider import usage_as_dicts as skill_usage_as_dicts

        result_extra["skill_index_count"] = len(skill_runtime.index)
        result_extra["skill_usage"] = skill_usage_as_dicts(skill_runtime.usage)
    if include_trace:
        result_extra["orchestrator_user_prompt"] = user_message
        result_extra["plan_steps"] = [
            {
                "tool_name": "deep_agents",
                "arguments": {"instruction": question},
                "success_criteria": question,
            }
        ]
        result_extra["planner_raw"] = json.dumps(
            {"harness": "deep_agents", "run_key": run_key},
            indent=2,
        )
        result_extra["harness_messages"] = _trace_messages(raw_result)
        result_extra["verification"] = {
            "verified": verification.verified,
            "method": verification.method,
            "reason": verification.reason,
        }

    logger.info(
        "harness_done client_id=%s status=%s delivered=%s reason=%s",
        cid,
        status,
        len(delivered),
        verification.reason,
    )
    return AgentResult(
        role="facade",
        client_id=cid,
        status=status,
        message=answer or verification.reason or status,
        extra=result_extra,
    )
