"""Executor tool discovery, lookup, and invoke.

Tool discovery is DB-driven via ``tool_registry`` (or injected at runtime
for tests). ``kind=code`` tools are executed by built-in in-process
handlers keyed by tool name (for example ``search_knowledge``).

``ToolDiscovery`` is the abstract protocol; ``DbToolDiscovery`` is the
concrete implementation backed by Postgres. The executor and orchestrator
use the protocol only.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from api.app.db.models import McpServer, ToolRegistry, WorkflowTemplate
from api.app.db.tool_store import (
    get_mcp_server,
    get_tool_registry,
    list_mcp_servers,
    list_tool_registry,
)
from api.app.logging_config import get_logger

logger = get_logger("api.agent.tools")

MAX_RESULT_CHARS = 4000

_STORE_NAMES = frozenset({"store_workflow", "store_from_attached_evidence"})

ToolFn = Callable[..., Any]


def _search_knowledge_result_to_dict(result: Any) -> dict[str, Any]:
    """JSON-safe shape for executor persistence (no mcp_server import)."""
    hits: list[dict[str, Any]] = []
    for c in getattr(result, "hits", None) or []:
        hits.append(
            {
                "point_id": c.point_id,
                "score": c.score,
                "text": c.text,
                "kind": c.kind,
                "client_id": c.client_id,
                "label": c.short_label(),
                "channel": c.channel,
                "ts": c.ts,
                "user": c.user,
                "thread_ts": c.thread_ts,
                "filename": c.filename,
                "locator": c.locator,
                "title": c.title,
                "source_format": c.source_format,
                "chunk_index": c.chunk_index,
            }
        )
    return {
        "ok": True,
        "client_id": result.client_id,
        "query": result.query,
        "limit": result.limit,
        "hit_count": len(hits),
        "hits": hits,
    }


def _invoke_search_knowledge(arguments: dict[str, Any]) -> dict[str, Any]:
    """In-process RAG: TEI embed + tenant-scoped vector search."""
    from api.app.retrieval import KnowledgeSearchFilters, search_knowledge

    query = str(arguments.get("query") or arguments.get("question") or "").strip()
    if not query:
        return {"ok": False, "error": "query must be non-empty"}

    limit_raw = arguments.get("limit", 8)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        limit = 8

    filters = KnowledgeSearchFilters.from_mapping(
        {
            "kind": arguments.get("kind"),
            "channel": arguments.get("channel"),
            "filename": arguments.get("filename"),
        }
    )
    result = search_knowledge(
        client_id=str(arguments.get("client_id") or "").strip() or None,
        query=query,
        limit=limit,
        filters=filters,
    )
    return _search_knowledge_result_to_dict(result)


_CODE_HANDLERS: dict[str, ToolFn] = {
    "search_knowledge": _invoke_search_knowledge,
}


class ToolExecutionError(Exception):
    """A found tool could not be run (distinct from lookup miss)."""


@dataclass(frozen=True)
class ToolRef:
    """A resolved tool. ``invoke`` is set for injected / in-memory handlers."""

    name: str
    source: str
    kind: str | None = None
    description: str | None = None
    invoke: ToolFn | None = None
    config: dict[str, Any] | None = None
    mcp_server_id: UUID | None = None


@runtime_checkable
class ToolDiscovery(Protocol):
    """Abstract tool discovery — callers depend on this, not on DB details."""

    def find(self, name: str, *, client_id: str) -> ToolRef | None:
        """Look up a tool by name for a tenant. Returns None if not found."""
        ...

    def list_tools(self, *, client_id: str) -> list[ToolRef]:
        """List all tools available for a tenant."""
        ...


class DbToolDiscovery:
    """Concrete tool discovery backed by ``tool_registry`` + ``mcp_servers``."""

    def __init__(
        self,
        db: Session,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._db = db
        self._extra = extra or {}

    def find(self, name: str, *, client_id: str) -> ToolRef | None:
        return lookup_tool(name, client_id=client_id, db=self._db, extra=self._extra)

    def list_tools(self, *, client_id: str) -> list[ToolRef]:
        injected = _injected_tools(self._extra)
        refs: list[ToolRef] = []

        for tool_name, fn in injected.items():
            refs.append(ToolRef(name=tool_name, source="injected", kind="code", invoke=fn))

        for row in list_tool_registry(self._db, tenant_id=client_id):
            if any(r.name == row.name for r in refs):
                continue
            refs.append(ToolRef(
                name=row.name,
                source="registry",
                kind=row.kind,
                description=row.description,
                config=row.config if isinstance(row.config, dict) else None,
                mcp_server_id=row.mcp_server_id,
            ))

        for server in list_mcp_servers(self._db, tenant_id=client_id):
            if not server.enabled:
                continue
            for tool_name in _mcp_tool_names(server, self._extra):
                if any(r.name == tool_name for r in refs):
                    continue
                refs.append(
                    ToolRef(
                        name=tool_name,
                        source="mcp",
                        kind="mcp",
                        mcp_server_id=server.id,
                    )
                )

        return refs


def _injected_tools(extra: dict[str, Any]) -> dict[str, ToolFn]:
    raw = extra.get("tools")
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if callable(v)}
    return {}


def _mcp_tool_names(server: McpServer, extra: dict[str, Any]) -> list[str]:
    """List tools on one already-configured MCP server via its lister."""
    lister = extra.get("mcp_list_tools")
    if callable(lister):
        names = lister(server)
        if names is None:
            return []
        return [str(n) for n in names]
    return []


def lookup_tool(
    name: str,
    *,
    client_id: str,
    db: Session,
    extra: dict[str, Any] | None = None,
) -> ToolRef | None:
    """Resolve ``name`` for ``client_id``. ``None`` if not found.

    Lookup order:
    1. Injected tools (test / runtime overrides via ``extra["tools"]``)
    2. ``tool_registry`` DB table (tenant-scoped)
    3. Enabled ``mcp_servers`` for the tenant (via lister callback)

    Built-in ``kind=code`` handlers (for example ``search_knowledge``) run
    only after a matching registry or injected tool is resolved.
    """
    tool_name = (name or "").strip()
    if not tool_name:
        return None
    extra = extra or {}

    injected = _injected_tools(extra)
    if tool_name in injected:
        return ToolRef(
            name=tool_name,
            source="injected",
            kind="code",
            invoke=injected[tool_name],
        )

    # Built-in host tool: real uvx install-and-run (no tool_registry row).
    if tool_name == "run_uvx":
        from api.app.agent.uvx_runner import run_uvx_from_arguments

        return ToolRef(
            name="run_uvx",
            source="builtin",
            kind="code",
            description="Run a PyPI CLI via real uvx / uv tool run",
            invoke=run_uvx_from_arguments,
        )

    row: ToolRegistry | None = get_tool_registry(
        db, tenant_id=client_id, name=tool_name
    )
    if row is not None:
        invoke = injected.get(tool_name)
        return ToolRef(
            name=row.name,
            source="registry",
            kind=row.kind,
            description=row.description,
            invoke=invoke,
            config=row.config if isinstance(row.config, dict) else None,
            mcp_server_id=row.mcp_server_id,
        )

    for server in list_mcp_servers(db, tenant_id=client_id):
        if not server.enabled:
            continue
        if tool_name in _mcp_tool_names(server, extra):
            return ToolRef(
                name=tool_name,
                source="mcp",
                kind="mcp",
                invoke=injected.get(tool_name),
                mcp_server_id=server.id,
            )

    logger.info("tool_lookup_miss client_id=%s name=%s", client_id, tool_name)
    return None


def small_result(value: Any) -> dict[str, Any]:
    """Persist a bounded JSON result (no unbounded dumps)."""
    if value is None:
        payload: dict[str, Any] = {"ok": True}
    elif isinstance(value, dict):
        payload = dict(value)
    else:
        payload = {"ok": True, "value": str(value)}
    encoded = json.dumps(payload, default=str)
    if len(encoded) > MAX_RESULT_CHARS:
        return {
            "ok": True,
            "truncated": True,
            "preview": encoded[: MAX_RESULT_CHARS // 2],
        }
    return payload


def result_error(result: Any) -> str | None:
    """Treat explicit ``ok``/``success`` false as a failed step."""
    if not isinstance(result, dict):
        return None
    if result.get("unavailable") is True:
        return None
    if result.get("ok") is False:
        return str(result.get("error") or "tool returned ok=false")
    if result.get("success") is False:
        return str(result.get("error") or "tool returned success=false")
    return None


def is_unavailable_result(result: Any) -> bool:
    """True when an MCP/server-disabled invoke returned a soft-unavailable payload."""
    return isinstance(result, dict) and result.get("unavailable") is True


def tool_result_message(tool_name: str, result: Any) -> str:
    """User-facing text from a tool result for Slack / final composition."""
    if not isinstance(result, dict):
        return str(result)
    if result.get("unavailable") is True:
        return str(result.get("error") or f"tool {tool_name} was unavailable")
    for key in ("text", "content", "message", "stdout", "value"):
        val = result.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    hits = result.get("hits")
    if isinstance(hits, list) and hits:
        parts = [
            str(h.get("text") or h.get("label") or "").strip()
            for h in hits
            if isinstance(h, dict)
        ]
        joined = "\n".join(p for p in parts if p)
        if joined:
            return joined
    # Structured external MCP payloads often have no text key — surface JSON.
    if result:
        try:
            import json

            return json.dumps(result, default=str)
        except Exception:
            return str(result)
    return ""


def _invoke_callable(fn: ToolFn, arguments: dict[str, Any]) -> Any:
    try:
        return fn(**arguments)
    except TypeError:
        return fn(arguments)


def _store_workflow(
    arguments: dict[str, Any], *, client_id: str, db: Session
) -> dict[str, Any]:
    title = str(arguments.get("title") or "Stored workflow")[:255]
    body = arguments.get("body_text")
    if body is None:
        body = arguments.get("body") or ""
    filename = str(arguments.get("filename") or "workflow.txt")[:255]
    rel = str(arguments.get("storage_relative_path") or f"workflows/{uuid4()}.txt")
    digest = str(arguments.get("content_hash") or f"executor-store-{uuid4().hex[:16]}")
    now = datetime.now(timezone.utc)
    row = WorkflowTemplate(
        tenant_id=UUID(str(client_id)),
        title=title,
        storage_relative_path=rel,
        content_hash=digest,
        original_filename=filename,
        body_text=str(body),
        visibility="shared",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    return {"ok": True, "id": str(row.id), "title": row.title}


def _unavailable_payload(tool_name: str, reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "unavailable": True,
        "error": f"tool {tool_name} was unavailable: {reason}",
    }


def _normalize_mcp_payload(raw: Any) -> Any:
    """Convert MCP SDK / FastMCP results into a plain dict when possible."""
    if isinstance(raw, dict):
        return raw
    try:
        from api.app.agent.mcp_client import tool_result_payload

        return tool_result_payload(raw)
    except Exception:
        text_parts: list[str] = []
        for block in getattr(raw, "content", None) or []:
            t = getattr(block, "text", None)
            if t:
                text_parts.append(str(t))
        if text_parts:
            return {"ok": True, "text": "\n".join(text_parts)}
        return {"ok": True, "value": str(raw)}


def _invoke_mcp(
    ref: ToolRef,
    arguments: dict[str, Any],
    *,
    client_id: str,
    db: Session,
    extra: dict[str, Any],
) -> Any:
    """Invoke an MCP tool via its linked ``mcp_servers`` row.

    Never falls back to the bundled ``mcp_client`` path.
    """
    server: McpServer | None = None
    if ref.mcp_server_id is not None:
        server = get_mcp_server(
            db, tenant_id=client_id, server_id=ref.mcp_server_id
        )

    if server is not None and not server.enabled:
        return _unavailable_payload(
            ref.name, f"MCP server {server.name!r} is disabled"
        )

    injected = extra.get("call_mcp_tool")
    if callable(injected):
        try:
            return injected(ref.name, arguments, server)
        except TypeError:
            return injected(ref.name, arguments)

    if server is None:
        raise ToolExecutionError(
            f"MCP tool {ref.name!r} has no linked mcp_servers row"
        )

    from api.app.agent.mcp_host import McpHostError, call_registered_mcp_tool

    cfg = (
        server.connection_config
        if isinstance(server.connection_config, dict)
        else None
    )
    # Do not forward executor-internal keys to remote MCP schemas.
    mcp_arguments = {
        key: value
        for key, value in arguments.items()
        if key not in {"client_id", "prior_step_results"}
    }
    try:
        raw = call_registered_mcp_tool(
            server_name=server.name,
            transport=server.transport,
            connection_config=cfg,
            enabled=server.enabled,
            tool_name=ref.name,
            arguments=mcp_arguments,
        )
    except McpHostError as exc:
        if getattr(exc, "code", None) == "server_disabled":
            return _unavailable_payload(ref.name, str(exc))
        raise ToolExecutionError(
            f"MCP tool {ref.name!r} failed: {exc}"
        ) from exc

    return _normalize_mcp_payload(raw)


def _normalize_cli_path(raw: str | Path) -> Path:
    """Resolve a config or argument path to a native absolute path."""
    text = str(raw).strip()
    if not text:
        return Path.cwd().resolve()
    # MSYS/Git-Bash style paths: /c/Users/foo -> C:\Users\foo on Windows.
    if (
        os.name == "nt"
        and len(text) >= 4
        and text[0] == "/"
        and text[1].isalpha()
        and text[2] == "/"
    ):
        text = f"{text[1].upper()}:{os.sep}{text[3:].replace('/', os.sep)}"
    return Path(text).expanduser().resolve()


def _looks_like_path_arg(arg: str) -> bool:
    if not arg or arg.startswith("-"):
        return False
    if "/" in arg or "\\" in arg:
        return True
    return bool("." in arg and not arg.startswith("."))


def _resolve_cli_working_dir(config: dict[str, Any], settings: Any) -> Path:
    """Pick a subprocess cwd: registry config, then cwd, then upload dir."""
    raw = config.get("working_dir")
    if raw:
        path = _normalize_cli_path(raw)
        if path.is_dir():
            return path
    cwd = Path.cwd().resolve()
    if cwd.is_dir():
        return cwd
    upload = settings.upload_dir_path.resolve()
    if upload.is_dir():
        return upload
    return cwd


def _resolve_cli_args(
    args_list: list[Any],
    *,
    working_dir: Path,
    search_dirs: list[Path],
) -> list[str]:
    """Resolve relative file paths in CLI args to native absolute paths."""
    resolved: list[str] = []
    bases = [working_dir, *[d for d in search_dirs if d != working_dir]]
    for arg in args_list:
        text = str(arg)
        if not _looks_like_path_arg(text):
            resolved.append(text)
            continue
        path = Path(text)
        if path.is_absolute():
            resolved.append(str(_normalize_cli_path(path)))
            continue
        hit: Path | None = None
        for base in bases:
            candidate = _normalize_cli_path(base / text)
            if candidate.exists():
                hit = candidate
                break
        resolved.append(str(hit if hit is not None else _normalize_cli_path(working_dir / text)))
    return resolved


def _resolve_cli_output_path(raw: str, working_dir: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return _normalize_cli_path(path)
    return _normalize_cli_path(working_dir / raw)


def _invoke_cli(ref: ToolRef, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a CLI tool as a subprocess using config from the registry."""
    from api.app.settings import get_settings

    settings = get_settings()
    if not settings.cli_tools_enabled:
        raise ToolExecutionError("CLI tool execution is disabled")

    config = ref.config or {}
    command = arguments.get("subcommand") or config.get("command")
    if not command:
        raise ToolExecutionError(f"no command specified for CLI tool {ref.name!r}")

    args_list = arguments.get("args_list") or arguments.get("args") or config.get("args", [])
    if isinstance(args_list, str):
        args_list = shlex.split(args_list)

    working_dir = _resolve_cli_working_dir(config, settings)
    search_dirs = [
        settings.upload_dir_path.resolve(),
        Path.cwd().resolve(),
    ]
    args_list = _resolve_cli_args(list(args_list), working_dir=working_dir, search_dirs=search_dirs)
    timeout = config.get("timeout_seconds") or settings.cli_tools_timeout_seconds

    cmd = [command] + list(args_list)
    logger.info("cli_exec tool=%s cmd=%s cwd=%s", ref.name, cmd, working_dir)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(working_dir),
        )
    except FileNotFoundError:
        raise ToolExecutionError(f"command not found: {command!r}")
    except subprocess.TimeoutExpired:
        raise ToolExecutionError(
            f"CLI tool {ref.name!r} timed out after {timeout}s"
        )

    stdout = result.stdout[: settings.cli_tools_max_output_bytes]
    stderr = result.stderr[:2000]

    if result.returncode != 0:
        return {
            "ok": False,
            "exit_code": result.returncode,
            "error": stderr or f"exit code {result.returncode}",
            "stdout": stdout,
        }

    output_file = arguments.get("output_file")
    if output_file and stdout:
        out_path = _resolve_cli_output_path(str(output_file), working_dir)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(stdout, encoding="utf-8")
        logger.info("cli_output_written tool=%s path=%s", ref.name, out_path)
        return {"ok": True, "exit_code": 0, "output_file": str(out_path), "bytes_written": len(stdout)}

    # Check for files the command created directly (not via stdout)
    expected_output = arguments.get("expected_output_path")
    if expected_output:
        expected = _resolve_cli_output_path(str(expected_output), working_dir)
        if expected.exists():
            return {
                "ok": True,
                "exit_code": 0,
                "output_file": str(expected),
                "bytes_written": expected.stat().st_size,
                "stdout": stdout,
            }
        else:
            return {
                "ok": False,
                "exit_code": 0,
                "error": f"command succeeded but expected output file not found: {expected}",
                "stdout": stdout,
            }

    return {"ok": True, "exit_code": 0, "stdout": stdout, "stderr": stderr}


def invoke_tool(
    ref: ToolRef,
    arguments: dict[str, Any] | None,
    *,
    client_id: str,
    db: Session,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a resolved tool. Always passes ``client_id`` into arguments."""
    extra = extra or {}
    args = dict(arguments or {})
    args.setdefault("client_id", client_id)
    try:
        if ref.invoke is not None:
            raw = _invoke_callable(ref.invoke, args)
        elif ref.name in _STORE_NAMES:
            raw = _store_workflow(args, client_id=client_id, db=db)
        elif ref.source == "mcp" or ref.kind == "mcp":
            raw = _invoke_mcp(
                ref, args, client_id=client_id, db=db, extra=extra
            )
        elif ref.kind == "cli":
            raw = _invoke_cli(ref, args)
        elif ref.kind == "code":
            handler = _CODE_HANDLERS.get(ref.name)
            if handler is None:
                raise ToolExecutionError(
                    f"no handler for tool {ref.name!r} (kind={ref.kind!r})"
                )
            raw = _invoke_callable(handler, args)
        else:
            raise ToolExecutionError(
                f"no handler for tool {ref.name!r} (kind={ref.kind!r})"
            )
    except ToolExecutionError:
        raise
    except Exception as exc:
        raise ToolExecutionError(f"tool {ref.name!r} failed: {exc}") from exc
    return small_result(raw)
