"""Tenant-scoped MCP tools for Deep Agents — available servers only.

Org Rep selects which MCP installs are available (enabled). At run time the
harness loads tools from those servers, prefers necessary use after list_tools,
and records a usage trace without secrets.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.agent.mcp_host import call_registered_mcp_tool, check_mcp_server
from api.app.db.tool_store import decrypt_mcp_server_secret, list_mcp_servers
from api.app.logging_config import get_logger
from api.app.mcp_servers.oauth import access_token_for_mcp_server
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.tenant_mcp")

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass
class McpUsageEvent:
    tenant_id: str
    run_key: str
    server_name: str
    tool_name: str
    step: str
    ok: bool
    detail: str | None = None


@dataclass
class TenantMcpRuntime:
    tools: list[Any] = field(default_factory=list)
    usage: list[McpUsageEvent] = field(default_factory=list)
    server_summaries: list[dict[str, Any]] = field(default_factory=list)


def _tool_id(server_name: str, tool_name: str) -> str:
    safe_server = _SAFE_NAME.sub("_", server_name).strip("_") or "server"
    safe_tool = _SAFE_NAME.sub("_", tool_name).strip("_") or "tool"
    return f"mcp__{safe_server}__{safe_tool}"


def _normalize_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return dict(arguments)
    if isinstance(arguments, str):
        text = arguments.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"input": arguments}
        return dict(parsed) if isinstance(parsed, dict) else {"input": parsed}
    return {"input": arguments}


def build_tenant_mcp_runtime(
    db: Session,
    *,
    tenant_id: str | UUID,
    run_key: str,
    settings: Settings | None = None,
) -> TenantMcpRuntime:
    """List tools on enabled tenant MCP servers and wrap them for Deep Agents."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class McpArguments(BaseModel):
        arguments: dict[str, Any] = Field(
            default_factory=dict,
            description="JSON object of arguments for the remote MCP tool",
        )

    cfg = settings or get_settings()
    tid = str(tenant_id)
    runtime = TenantMcpRuntime()
    rows = [r for r in list_mcp_servers(db, tenant_id=tid) if r.enabled]
    timeout = float(cfg.mcp_host_check_timeout_seconds)

    for row in rows:
        conn = row.connection_config if isinstance(row.connection_config, dict) else None
        service = decrypt_mcp_server_secret(row, cfg)
        token = access_token_for_mcp_server(row, cfg, service_token=service)
        probe = check_mcp_server(
            server_name=row.name,
            transport=row.transport,
            connection_config=conn,
            enabled=True,
            timeout_seconds=timeout,
            service_token=token,
        )
        summary = {
            "server_name": row.name,
            "ready": probe.ready,
            "tool_names": list(probe.tool_names),
            "error": probe.error,
        }
        runtime.server_summaries.append(summary)
        if not probe.ready:
            logger.info(
                "tenant_mcp_skip_not_ready tenant=%s server=%s err=%s",
                tid,
                row.name,
                probe.error,
            )
            continue

        defs_by_name = {
            str(d.get("name")): d
            for d in (probe.tool_defs or [])
            if isinstance(d, dict) and d.get("name")
        }
        for tool_name in probe.tool_names:
            tool_id = _tool_id(row.name, tool_name)
            tool_def = defs_by_name.get(tool_name) or {}
            remote_desc = str(tool_def.get("description") or "").strip()
            schema = tool_def.get("inputSchema") if isinstance(tool_def.get("inputSchema"), dict) else {}
            description = (
                f"MCP tool {tool_name!r} on tenant server {row.name!r}. "
                "Use only when necessary for the user request."
            )
            if remote_desc:
                description = f"{description} {remote_desc}"
            if schema:
                description = f"{description} inputSchema={json.dumps(schema)[:800]}"

            def _make_caller(
                *,
                server_row=row,
                remote_tool=tool_name,
                bound_token=token,
                bound_conn=conn,
            ) -> Callable[..., str]:
                def _call(arguments: dict[str, Any] | None = None) -> str:
                    payload = _normalize_arguments(arguments)
                    try:
                        raw = call_registered_mcp_tool(
                            server_name=server_row.name,
                            transport=server_row.transport,
                            connection_config=bound_conn,
                            enabled=True,
                            tool_name=remote_tool,
                            arguments=payload,
                            timeout_seconds=float(
                                getattr(cfg, "agent_mcp_timeout_seconds", None) or 60.0
                            ),
                            service_token=bound_token,
                        )
                        runtime.usage.append(
                            McpUsageEvent(
                                tenant_id=tid,
                                run_key=run_key,
                                server_name=server_row.name,
                                tool_name=remote_tool,
                                step="tool_call",
                                ok=True,
                            )
                        )
                        logger.info(
                            "mcp_usage tenant=%s run_key=%s server=%s tool=%s",
                            tid,
                            run_key,
                            server_row.name,
                            remote_tool,
                        )
                        return str(raw)
                    except Exception as exc:
                        runtime.usage.append(
                            McpUsageEvent(
                                tenant_id=tid,
                                run_key=run_key,
                                server_name=server_row.name,
                                tool_name=remote_tool,
                                step="tool_call",
                                ok=False,
                                detail=str(exc),
                            )
                        )
                        logger.info(
                            "mcp_usage_failed tenant=%s run_key=%s server=%s tool=%s err=%s",
                            tid,
                            run_key,
                            server_row.name,
                            remote_tool,
                            exc,
                        )
                        return f"MCP tool error: {exc}"

                return _call

            runtime.tools.append(
                StructuredTool.from_function(
                    func=_make_caller(),
                    name=tool_id,
                    description=description,
                    args_schema=McpArguments,
                )
            )

    logger.info(
        "tenant_mcp_runtime tenant=%s run_key=%s servers=%s tools=%s",
        tid,
        run_key,
        len(runtime.server_summaries),
        len(runtime.tools),
    )
    return runtime


def usage_as_dicts(events: list[McpUsageEvent]) -> list[dict[str, Any]]:
    return [
        {
            "tenant_id": e.tenant_id,
            "run_key": e.run_key,
            "server_name": e.server_name,
            "tool_name": e.tool_name,
            "step": e.step,
            "ok": e.ok,
            "detail": e.detail,
        }
        for e in events
    ]
