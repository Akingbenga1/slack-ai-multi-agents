"""MCP client Adapter — LangGraph tools talk to bundled MCP tools.

Transport (Sprint 27.3): one ``invoke_mcp`` Adapter. Prefer in-process
FastMCP for API/worker; stdio remains for external clients / opt-in.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import sys
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from api.app.logging_config import get_logger
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from api.app.settings import Settings, get_settings
from api.app.tenant import get_client_id

logger = get_logger("api.agent.mcp_client")

# Injected in tests: async (name, arguments) -> CallToolResult-like or structured dict
McpCallTool = Callable[[str, dict[str, Any]], Awaitable[Any]]

REPO_ROOT = Path(__file__).resolve().parents[3]

# Cached FastMCP for in-process transport (one process-local Adapter instance).
_in_process_mcp: Any | None = None
_mcp_sync_pool: concurrent.futures.ThreadPoolExecutor | None = None


def _sync_mcp_pool() -> concurrent.futures.ThreadPoolExecutor:
    global _mcp_sync_pool
    if _mcp_sync_pool is None:
        _mcp_sync_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="mcp-sync",
        )
    return _mcp_sync_pool


def mcp_server_params(
    settings: Settings | None = None,
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> StdioServerParameters:
    """
    Stdio launch for ``python -m mcp_server``.

    Uses the current interpreter so the child shares the same venv.
    Optional ``settings.agent_mcp_command`` / ``agent_mcp_args`` override.
    """
    settings = settings or get_settings()
    command = (settings.agent_mcp_command or sys.executable).strip() or sys.executable
    raw_args = (settings.agent_mcp_args or "").strip()
    if raw_args:
        args = raw_args.split()
    else:
        args = ["-m", "mcp_server"]
    child_env = dict(env) if env is not None else dict(os.environ)
    return StdioServerParameters(
        command=command,
        args=args,
        cwd=str(cwd or REPO_ROOT),
        env=child_env,
    )


def _mcp_transport(settings: Settings | None) -> str:
    settings = settings or get_settings()
    raw = (getattr(settings, "agent_mcp_transport", None) or "in_process").strip()
    return raw.lower().replace("-", "_")


def _in_process_server() -> Any:
    global _in_process_mcp
    if _in_process_mcp is None:
        from mcp_server.server import create_mcp

        _in_process_mcp = create_mcp()
    return _in_process_mcp


async def call_mcp_tool_async(
    name: str,
    arguments: dict[str, Any],
    *,
    settings: Settings | None = None,
    server: StdioServerParameters | None = None,
    call_tool: Optional[McpCallTool] = None,
) -> CallToolResult | Any:
    """Call one MCP tool (in-process, stdio, or injectable ``call_tool``)."""
    if call_tool is not None:
        return await call_tool(name, arguments)

    settings = settings or get_settings()
    timeout = float(getattr(settings, "agent_mcp_timeout_seconds", 60.0) or 60.0)
    transport = _mcp_transport(settings)

    async def _invoke() -> CallToolResult | Any:
        if transport in ("in_process", "inprocess", "local"):
            app = _in_process_server()
            return await app.call_tool(name, arguments)

        params = server or mcp_server_params(settings)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(name, arguments)

    try:
        return await asyncio.wait_for(_invoke(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"MCP tool {name!r} timed out after {timeout:.1f}s"
        ) from exc


def call_mcp_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    settings: Settings | None = None,
    server: StdioServerParameters | None = None,
    call_tool: Optional[McpCallTool] = None,
) -> CallToolResult | Any:
    """Sync wrapper for LangGraph sync nodes (running-loop safe)."""
    settings = settings or get_settings()
    timeout = float(getattr(settings, "agent_mcp_timeout_seconds", 60.0) or 60.0)
    coro = call_mcp_tool_async(
        name,
        arguments,
        settings=settings,
        server=server,
        call_tool=call_tool,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Already inside an event loop — bridge via a shared worker pool.
    future = _sync_mcp_pool().submit(asyncio.run, coro)
    try:
        return future.result(timeout=timeout + 5.0)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise TimeoutError(
            f"MCP tool {name!r} sync bridge timed out after {timeout + 5.0:.1f}s"
        ) from exc


def _assert_mcp_client_id(arguments: dict[str, Any]) -> None:
    """Fail-closed when tool args disagree with request/task tenant context."""
    raw = arguments.get("client_id")
    if not raw:
        return
    ctx = (get_client_id() or "").strip()
    bound = (os.environ.get("MCP_BOUND_CLIENT_ID") or "").strip()
    expected = ctx or bound
    if not expected:
        return
    try:
        if str(UUID(str(raw))) != str(UUID(expected)):
            raise PermissionError(
                f"MCP client_id mismatch: tool={raw!r} context={expected!r}"
            )
    except ValueError as exc:
        raise PermissionError(f"Invalid MCP client_id: {raw!r}") from exc


def invoke_mcp(
    name: str,
    arguments: dict[str, Any],
    *,
    settings: Settings | None = None,
    call_tool: Optional[McpCallTool] = None,
    server: StdioServerParameters | None = None,
) -> dict[str, Any]:
    """
    Thin Adapter: call one MCP tool and return its structured payload.

    Tool Strategies / typed helpers should use this (or a thin wrapper) and
    must not own transport details.
    """
    _assert_mcp_client_id(arguments)
    logger.info("mcp_call_tool name=%s", name)
    raw = call_mcp_tool(
        name,
        arguments,
        settings=settings,
        server=server,
        call_tool=call_tool,
    )
    return tool_result_payload(raw)


def tool_result_payload(result: Any) -> dict[str, Any]:
    """Extract structured JSON from a CallToolResult (or pass-through dict)."""
    if isinstance(result, dict):
        return result
    # FastMCP in-process: (content_blocks, structured_dict)
    if (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[1], dict)
    ):
        return result[1]
    if getattr(result, "isError", False):
        text = _content_text(result)
        raise RuntimeError(f"MCP tool error: {text or result!r}")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    text = _content_text(result)
    if text:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    raise RuntimeError("MCP tool returned no structured content")


def _content_text(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        t = getattr(block, "text", None)
        if t:
            parts.append(str(t))
    return "\n".join(parts).strip()


def citation_from_mcp_hit(hit: Mapping[str, Any]) -> KnowledgeCitation:
    """Rebuild a citation from MCP ``search_knowledge`` hit dict."""
    return KnowledgeCitation(
        point_id=str(hit.get("point_id") or ""),
        score=float(hit.get("score") or 0.0),
        text=str(hit.get("text") or ""),
        kind=str(hit.get("kind") or "unknown"),
        client_id=str(hit.get("client_id") or ""),
        channel=hit.get("channel"),
        ts=hit.get("ts"),
        user=hit.get("user"),
        thread_ts=hit.get("thread_ts"),
        filename=hit.get("filename"),
        locator=hit.get("locator"),
        title=hit.get("title"),
        source_format=hit.get("source_format"),
        chunk_index=hit.get("chunk_index"),
    )


def knowledge_result_from_mcp(payload: Mapping[str, Any]) -> KnowledgeSearchResult:
    hits_raw = payload.get("hits") or []
    hits = [citation_from_mcp_hit(h) for h in hits_raw if isinstance(h, Mapping)]
    return KnowledgeSearchResult(
        client_id=str(payload.get("client_id") or ""),
        query=str(payload.get("query") or ""),
        hits=hits,
        limit=int(payload.get("limit") or len(hits)),
    )


def _optional_args(**kwargs: Any) -> dict[str, Any]:
    """Drop falsy values so MCP schemas do not get unexpected nulls/empties."""
    return {k: v for k, v in kwargs.items() if v}


def search_knowledge_via_mcp(
    *,
    client_id: str,
    query: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    filename: str | None = None,
    settings: Settings | None = None,
    call_tool: Optional[McpCallTool] = None,
    score_threshold: float | None = None,
    **_ignored: Any,
) -> KnowledgeSearchResult:
    """
    ``SearchFn``-compatible wrapper: invoke MCP ``search_knowledge``.

    ``score_threshold`` is applied by the retrieve/tools node after hits return
    (MCP tool does not filter by score today).
    """
    del score_threshold  # used by retrieve node, not MCP args
    args: dict[str, Any] = {
        "client_id": client_id,
        "query": query,
        "limit": int(limit),
        **_optional_args(kind=kind, channel=channel, filename=filename),
    }
    payload = invoke_mcp(
        "search_knowledge", args, settings=settings, call_tool=call_tool
    )
    return knowledge_result_from_mcp(payload)


def draft_meeting_brief_via_mcp(
    *,
    client_id: str,
    topic: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    settings: Settings | None = None,
    call_tool: Optional[McpCallTool] = None,
) -> dict[str, Any]:
    """Invoke MCP ``draft_meeting_brief`` (typed helper over ``invoke_mcp``)."""
    args: dict[str, Any] = {
        "client_id": client_id,
        "topic": topic,
        "limit": int(limit),
        **_optional_args(kind=kind, channel=channel),
    }
    return invoke_mcp(
        "draft_meeting_brief", args, settings=settings, call_tool=call_tool
    )


def draft_meeting_agenda_via_mcp(
    *,
    client_id: str,
    topic: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    settings: Settings | None = None,
    call_tool: Optional[McpCallTool] = None,
) -> dict[str, Any]:
    """Invoke MCP ``draft_meeting_agenda`` (typed helper over ``invoke_mcp``)."""
    args: dict[str, Any] = {
        "client_id": client_id,
        "topic": topic,
        "limit": int(limit),
        **_optional_args(kind=kind, channel=channel),
    }
    return invoke_mcp(
        "draft_meeting_agenda", args, settings=settings, call_tool=call_tool
    )


def draft_meeting_notes_via_mcp(
    *,
    client_id: str,
    topic: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    settings: Settings | None = None,
    call_tool: Optional[McpCallTool] = None,
) -> dict[str, Any]:
    """Invoke MCP ``draft_meeting_notes`` (typed helper over ``invoke_mcp``)."""
    args: dict[str, Any] = {
        "client_id": client_id,
        "topic": topic,
        "limit": int(limit),
        **_optional_args(kind=kind, channel=channel),
    }
    return invoke_mcp(
        "draft_meeting_notes", args, settings=settings, call_tool=call_tool
    )


def draft_report_via_mcp(
    *,
    client_id: str,
    window_label: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    topic: str | None = None,
    settings: Settings | None = None,
    call_tool: Optional[McpCallTool] = None,
) -> dict[str, Any]:
    """Invoke MCP ``draft_report`` (typed helper over ``invoke_mcp``)."""
    args: dict[str, Any] = {
        "client_id": client_id,
        "window_label": window_label,
        "limit": int(limit),
        **_optional_args(kind=kind, channel=channel, topic=topic),
    }
    return invoke_mcp(
        "draft_report", args, settings=settings, call_tool=call_tool
    )


def start_onboarding_via_mcp(
    *,
    client_id: str,
    settings: Settings | None = None,
    call_tool: Optional[McpCallTool] = None,
) -> dict[str, Any]:
    """Invoke MCP ``start_onboarding`` (typed helper over ``invoke_mcp``)."""
    return invoke_mcp(
        "start_onboarding",
        {"client_id": client_id},
        settings=settings,
        call_tool=call_tool,
    )


__all__ = [
    "McpCallTool",
    "call_mcp_tool",
    "call_mcp_tool_async",
    "citation_from_mcp_hit",
    "draft_meeting_agenda_via_mcp",
    "draft_meeting_brief_via_mcp",
    "draft_meeting_notes_via_mcp",
    "draft_report_via_mcp",
    "invoke_mcp",
    "knowledge_result_from_mcp",
    "mcp_server_params",
    "search_knowledge_via_mcp",
    "start_onboarding_via_mcp",
    "tool_result_payload",
]
