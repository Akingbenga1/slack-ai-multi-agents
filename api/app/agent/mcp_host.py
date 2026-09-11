"""MCP server readiness — probe registered servers (control plane).

Used by admin/ops endpoints only. The Deep Agents harness does not call
this; it only uses servers that are already reachable when needed.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from api.app.logging_config import get_logger

logger = get_logger("api.agent.mcp_host")  # noqa: keep module logger id stable

_PROBE_POOL: concurrent.futures.ThreadPoolExecutor | None = None


class McpHostError(Exception):
    """Raised when an MCP readiness check cannot proceed."""

    def __init__(self, message: str, *, code: str = "mcp_host_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class McpCheckResult:
    server_name: str
    transport: str
    ready: bool
    enabled: bool
    endpoint: str | None
    tool_count: int | None
    tool_names: list[str] = field(default_factory=list)
    tool_defs: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    detail: str | None = None


def _probe_pool() -> concurrent.futures.ThreadPoolExecutor:
    global _PROBE_POOL
    if _PROBE_POOL is None:
        _PROBE_POOL = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="mcp-host-probe",
        )
    return _PROBE_POOL


def as_config_dict(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def extract_http_url(config: dict[str, Any] | None) -> str | None:
    """Best-effort URL from discovery-style or explicit connection_config."""
    cfg = as_config_dict(config)
    for key in ("url", "endpoint", "base_url", "baseUrl"):
        val = cfg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    remotes = cfg.get("remotes")
    if isinstance(remotes, list):
        for remote in remotes:
            if not isinstance(remote, dict):
                continue
            url = remote.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
    return None


def extract_stdio_launch(
    config: dict[str, Any] | None,
) -> tuple[str, list[str], dict[str, str] | None] | None:
    """Return (command, args, env) when connection_config describes a stdio server."""
    cfg = as_config_dict(config)
    command = cfg.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    raw_args = cfg.get("args")
    args: list[str] = []
    if isinstance(raw_args, list):
        args = [str(a) for a in raw_args]
    elif isinstance(raw_args, str) and raw_args.strip():
        args = raw_args.split()
    env: dict[str, str] | None = None
    raw_env = cfg.get("env")
    if isinstance(raw_env, dict):
        env = {str(k): str(v) for k, v in raw_env.items()}
    return command.strip(), args, env


def extract_http_headers(config: dict[str, Any] | None) -> dict[str, str] | None:
    """Return non-secret HTTP headers from connection_config when present."""
    cfg = as_config_dict(config)
    raw = cfg.get("headers")
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, str) and key.strip() and value:
            out[key.strip()] = value
    return out or None


def merge_service_auth_headers(
    config: dict[str, Any] | None,
    *,
    service_token: str | None = None,
) -> dict[str, str] | None:
    """Build request headers: optional config headers + Bearer service credential."""
    headers = dict(extract_http_headers(config) or {})
    token = (service_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers or None


def _validate_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise McpHostError(
            f"unsupported URL scheme: {parsed.scheme or '(none)'!r}",
            code="invalid_url",
        )
    if not parsed.netloc:
        raise McpHostError("URL is missing a host", code="invalid_url")
    return url


def _split_tool_defs(defs: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    trimmed = defs[:50]
    names = [str(d.get("name") or "") for d in trimmed if d.get("name")]
    return names, trimmed


async def _list_tools_http(
    url: str,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(url, headers=headers, timeout=timeout) as (
        read,
        write,
        _get_session_id,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            out: list[dict[str, Any]] = []
            for t in listed.tools or []:
                schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None)
                out.append(
                    {
                        "name": t.name,
                        "description": getattr(t, "description", None) or "",
                        "inputSchema": schema if isinstance(schema, dict) else {},
                    }
                )
            return out


async def _list_tools_stdio(
    command: str,
    args: list[str],
    env: dict[str, str] | None,
    *,
    timeout: float,
) -> list[dict[str, Any]]:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    resolved = shutil.which(command) or command
    child_env = dict(os.environ)
    if env:
        child_env.update(env)
    params = StdioServerParameters(
        command=resolved,
        args=args,
        env=child_env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            out: list[dict[str, Any]] = []
            for t in listed.tools or []:
                schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None)
                out.append(
                    {
                        "name": t.name,
                        "description": getattr(t, "description", None) or "",
                        "inputSchema": schema if isinstance(schema, dict) else {},
                    }
                )
            return out


async def _http_fallback_reachable(url: str, *, timeout: float) -> None:
    """When full MCP handshake fails, still verify the endpoint accepts HTTP."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
        except httpx.RequestError as exc:
            raise McpHostError(f"HTTP unreachable: {exc}", code="unreachable") from exc
        if resp.status_code >= 500:
            raise McpHostError(
                f"HTTP {resp.status_code} from endpoint",
                code="http_error",
            )


def _run_async(coro: Any, *, timeout: float) -> Any:
    async def _bounded() -> Any:
        return await asyncio.wait_for(coro, timeout=timeout)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_bounded())

    future = _probe_pool().submit(asyncio.run, _bounded())
    try:
        return future.result(timeout=timeout + 5.0)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise McpHostError(
            f"MCP probe timed out after {timeout:.1f}s",
            code="timeout",
        ) from exc


def check_mcp_server(
    *,
    server_name: str,
    transport: str,
    connection_config: dict[str, Any] | None,
    enabled: bool,
    timeout_seconds: float = 20.0,
    service_token: str | None = None,
) -> McpCheckResult:
    """Probe one registered MCP server for initialize + list_tools readiness."""
    timeout = max(1.0, float(timeout_seconds))
    transport_norm = (transport or "").strip().lower() or "http"
    http_headers = merge_service_auth_headers(
        connection_config, service_token=service_token
    )

    if not enabled:
        return McpCheckResult(
            server_name=server_name,
            transport=transport_norm,
            ready=False,
            enabled=False,
            endpoint=None,
            tool_count=None,
            tool_names=[],
            error="server is disabled",
            detail="Enable the server, then run Check again.",
        )

    if transport_norm in {"http", "streamable-http", "sse", "websocket"}:
        url = extract_http_url(connection_config)
        if not url:
            return McpCheckResult(
                server_name=server_name,
                transport=transport_norm,
                ready=False,
                enabled=True,
                endpoint=None,
                tool_count=None,
                tool_names=[],
                error="missing URL in connection_config",
                detail="Set connection_config.url (or remotes[].url) before checking.",
            )
        try:
            url = _validate_http_url(url)
        except McpHostError as exc:
            return McpCheckResult(
                server_name=server_name,
                transport=transport_norm,
                ready=False,
                enabled=True,
                endpoint=url,
                tool_count=None,
                tool_names=[],
                error=str(exc),
                detail=exc.code,
            )
        try:
            defs = _run_async(
                _list_tools_http(url, timeout=timeout, headers=http_headers),
                timeout=timeout,
            )
            names, tool_defs = _split_tool_defs(defs)
            return McpCheckResult(
                server_name=server_name,
                transport=transport_norm,
                ready=True,
                enabled=True,
                endpoint=url,
                tool_count=len(names),
                tool_names=names,
                tool_defs=tool_defs,
                error=None,
                detail=f"initialize ok · {len(names)} tool(s)",
            )
        except Exception as exc:  # noqa: BLE001 — surface probe failures to UI
            logger.info(
                "mcp_host_http_handshake_failed server=%s err=%s",
                server_name,
                exc,
            )
            try:
                _run_async(
                    _http_fallback_reachable(url, timeout=min(timeout, 10.0)),
                    timeout=timeout,
                )
                return McpCheckResult(
                    server_name=server_name,
                    transport=transport_norm,
                    ready=False,
                    enabled=True,
                    endpoint=url,
                    tool_count=None,
                    tool_names=[],
                    error="endpoint reachable but MCP handshake failed",
                    detail=str(exc)[:400],
                )
            except McpHostError as reach_exc:
                return McpCheckResult(
                    server_name=server_name,
                    transport=transport_norm,
                    ready=False,
                    enabled=True,
                    endpoint=url,
                    tool_count=None,
                    tool_names=[],
                    error=str(reach_exc),
                    detail=str(exc)[:400],
                )
            except Exception as reach_exc:  # noqa: BLE001
                return McpCheckResult(
                    server_name=server_name,
                    transport=transport_norm,
                    ready=False,
                    enabled=True,
                    endpoint=url,
                    tool_count=None,
                    tool_names=[],
                    error=f"unreachable: {reach_exc}",
                    detail=str(exc)[:400],
                )

    if transport_norm in {"stdio", "std-io", "standard-io"}:
        launch = extract_stdio_launch(connection_config)
        if launch is None:
            return McpCheckResult(
                server_name=server_name,
                transport=transport_norm,
                ready=False,
                enabled=True,
                endpoint=None,
                tool_count=None,
                tool_names=[],
                error="missing command in connection_config",
                detail="Set connection_config.command (+ optional args) for stdio servers.",
            )
        command, args, env = launch
        which = shutil.which(command)
        if which is None and not os.path.isfile(command):
            return McpCheckResult(
                server_name=server_name,
                transport=transport_norm,
                ready=False,
                enabled=True,
                endpoint=command,
                tool_count=None,
                tool_names=[],
                error=f"command not found on PATH: {command}",
                detail="Install the MCP server binary, then Check again.",
            )
        endpoint = " ".join([command, *args]).strip()
        try:
            defs = _run_async(
                _list_tools_stdio(command, args, env, timeout=timeout),
                timeout=timeout,
            )
            names, tool_defs = _split_tool_defs(defs)
            return McpCheckResult(
                server_name=server_name,
                transport=transport_norm,
                ready=True,
                enabled=True,
                endpoint=endpoint,
                tool_count=len(names),
                tool_names=names,
                tool_defs=tool_defs,
                error=None,
                detail=f"initialize ok · {len(names)} tool(s)",
            )
        except Exception as exc:  # noqa: BLE001
            return McpCheckResult(
                server_name=server_name,
                transport=transport_norm,
                ready=False,
                enabled=True,
                endpoint=endpoint,
                tool_count=None,
                tool_names=[],
                error=f"stdio probe failed: {exc}",
                detail=str(exc)[:400],
            )

    return McpCheckResult(
        server_name=server_name,
        transport=transport_norm,
        ready=False,
        enabled=True,
        endpoint=None,
        tool_count=None,
        tool_names=[],
        error=f"unsupported transport: {transport_norm!r}",
        detail="Expected http or stdio.",
    )


async def _call_tool_http(
    url: str,
    name: str,
    arguments: dict[str, Any],
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
) -> Any:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(url, headers=headers, timeout=timeout) as (
        read,
        write,
        _get_session_id,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(name, arguments)


async def _call_tool_stdio(
    command: str,
    args: list[str],
    env: dict[str, str] | None,
    name: str,
    arguments: dict[str, Any],
    *,
    timeout: float,
) -> Any:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    resolved = shutil.which(command) or command
    child_env = dict(os.environ)
    if env:
        child_env.update(env)
    params = StdioServerParameters(
        command=resolved,
        args=args,
        env=child_env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(name, arguments)


def call_registered_mcp_tool(
    *,
    server_name: str,
    transport: str,
    connection_config: dict[str, Any] | None,
    enabled: bool,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float | None = None,
    service_token: str | None = None,
) -> Any:
    """Open a live MCP session from ``connection_config`` and call ``tool_name``.

    Never uses the bundled in-process MCP. Raises ``McpHostError`` when the
    server is disabled or connection_config cannot open a session.
    """
    from api.app.settings import get_settings

    timeout = float(
        timeout_seconds
        if timeout_seconds is not None
        else (getattr(get_settings(), "agent_mcp_timeout_seconds", None) or 60.0)
    )
    timeout = max(1.0, timeout)
    transport_norm = (transport or "").strip().lower() or "http"
    http_headers = merge_service_auth_headers(
        connection_config, service_token=service_token
    )

    if not enabled:
        raise McpHostError(
            f"MCP server {server_name!r} is disabled",
            code="server_disabled",
        )

    if transport_norm in {"http", "streamable-http", "sse", "websocket"}:
        url = extract_http_url(connection_config)
        if not url:
            raise McpHostError(
                f"MCP server {server_name!r} missing URL in connection_config",
                code="invalid_config",
            )
        url = _validate_http_url(url)
        logger.info(
            "mcp_registry_call transport=http server=%s tool=%s",
            server_name,
            tool_name,
        )
        return _run_async(
            _call_tool_http(
                url,
                tool_name,
                arguments,
                timeout=timeout,
                headers=http_headers,
            ),
            timeout=timeout,
        )

    if transport_norm in {"stdio", "std-io", "standard-io"}:
        launch = extract_stdio_launch(connection_config)
        if launch is None:
            raise McpHostError(
                f"MCP server {server_name!r} missing command in connection_config",
                code="invalid_config",
            )
        command, args, env = launch
        which = shutil.which(command)
        if which is None and not os.path.isfile(command):
            raise McpHostError(
                f"command not found on PATH: {command}",
                code="command_not_found",
            )
        logger.info(
            "mcp_registry_call transport=stdio server=%s tool=%s",
            server_name,
            tool_name,
        )
        return _run_async(
            _call_tool_stdio(command, args, env, tool_name, arguments, timeout=timeout),
            timeout=timeout,
        )

    raise McpHostError(
        f"unsupported MCP transport: {transport_norm!r}",
        code="unsupported_transport",
    )


def check_bundled_mcp(*, timeout_seconds: float = 20.0) -> McpCheckResult:
    """Probe the process-local / settings-backed bundled MCP used by the agent."""
    timeout = max(1.0, float(timeout_seconds))

    async def _probe() -> list[str]:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        from api.app.agent.mcp_client import (
            _in_process_server,
            _mcp_transport,
            mcp_server_params,
        )
        from api.app.settings import get_settings

        settings = get_settings()
        transport = _mcp_transport(settings)
        if transport in ("in_process", "inprocess", "local"):
            app = _in_process_server()
            listed = await app.list_tools()
            names: list[str] = []
            for item in listed or []:
                name = getattr(item, "name", None)
                if name:
                    names.append(str(name))
                elif isinstance(item, dict) and item.get("name"):
                    names.append(str(item["name"]))
            return names

        params = mcp_server_params(settings)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [t.name for t in (result.tools or [])]

    try:
        names = _run_async(_probe(), timeout=timeout)
        trimmed = names[:50]
        return McpCheckResult(
            server_name="__bundled__",
            transport="bundled",
            ready=True,
            enabled=True,
            endpoint=sys.executable,
            tool_count=len(names),
            tool_names=trimmed,
            tool_defs=[{"name": n, "description": "", "inputSchema": {}} for n in trimmed],
            error=None,
            detail=f"bundled MCP ready · {len(names)} tool(s)",
        )
    except Exception as exc:  # noqa: BLE001
        return McpCheckResult(
            server_name="__bundled__",
            transport="bundled",
            ready=False,
            enabled=True,
            endpoint=sys.executable,
            tool_count=None,
            tool_names=[],
            error=f"bundled MCP probe failed: {exc}",
            detail=str(exc)[:400],
        )
