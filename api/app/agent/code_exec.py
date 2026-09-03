"""Workspace actions executed on behalf of the ReAct loop.

Every action is provisioned through ``uvx``: ``run_python`` executes a
model-authored script under ``uvx --with <libs> python``, and ``run_cli``
executes a PyPI console script. Both return the same observation contract so
the loop, the verifier, and the trace treat them uniformly, and neither can
touch state outside the run workspace.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from api.app.agent.uvx_runner import UvxRunnerError, run_uvx
from api.app.agent.workspace import RunWorkspace
from api.app.logging_config import get_logger

logger = get_logger("api.agent.code_exec")

RUN_PYTHON_ACTION = "run_python"
RUN_CLI_ACTION = "run_uvx"
INSPECT_ACTION = "inspect_workspace"
FINISH_ACTION = "finish"

# The interpreter is itself provisioned by uvx, so no host Python is assumed.
PYTHON_ENTRYPOINT = "python"

_SAFE_LIB = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*(\[[A-Za-z0-9][A-Za-z0-9._,+-]*\])?$")
_MISSING_MODULE_RE = re.compile(
    r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
)
_TRACEBACK_LAST_RE = re.compile(r"^(\w+(?:Error|Exception|Warning))\b.*$", re.MULTILINE)
_PEEK_TEXT_SUFFIXES = frozenset(
    {".txt", ".csv", ".json", ".md", ".html", ".xml", ".yml", ".yaml", ".log", ".tsv", ".py"}
)


def _observation_limit(settings: Any) -> int:
    return max(500, int(getattr(settings, "executor_observation_chars", 4000) or 4000))


def _clip(text: Any, limit: int) -> str:
    """Keep head and tail of long output; the middle is rarely load-bearing."""
    body = str(text or "")
    if len(body) <= limit:
        return body
    head = body[: int(limit * 0.7)]
    tail = body[-int(limit * 0.25) :]
    dropped = len(body) - len(head) - len(tail)
    return f"{head}\n… [{dropped} characters omitted] …\n{tail}"


def validate_libs(raw: Any, *, settings: Any) -> tuple[list[str], str | None]:
    """Validate requested PyPI libraries against name rules and policy."""
    if isinstance(raw, str):
        candidates = [raw]
    else:
        candidates = list(raw or [])
    libs: list[str] = []
    for item in candidates:
        name = str(item or "").strip()
        if not name:
            continue
        if not _SAFE_LIB.match(name):
            return [], f"invalid library name: {name!r}"
        if name not in libs:
            libs.append(name)

    max_libs = max(1, int(getattr(settings, "agent_python_max_libs", 8) or 8))
    if len(libs) > max_libs:
        return [], f"too many libraries requested ({len(libs)} > {max_libs})"

    allowlist_raw = str(getattr(settings, "agent_python_libs_allowlist", "") or "").strip()
    if allowlist_raw:
        allowed = {
            part.strip().lower()
            for part in allowlist_raw.replace(",", " ").split()
            if part.strip()
        }
        blocked = [
            name for name in libs if name.split("[", 1)[0].lower() not in allowed
        ]
        if blocked:
            return [], f"libraries not permitted by policy: {', '.join(blocked)}"
    return libs, None


def classify_python_result(
    *,
    ok: bool,
    stdout: str,
    stderr: str,
    produced: Sequence[Path],
) -> dict[str, Any]:
    """Turn a script outcome into a typed, actionable observation."""
    if ok:
        if produced:
            return {"error_class": "success", "retryable": False, "suggested_next": ""}
        return {
            "error_class": "success_no_output",
            "retryable": True,
            "suggested_next": (
                "The script ran without error but produced no file. If the goal "
                "requires an artifact, write it to a relative path and re-run; if "
                "the goal is informational, the printed output is the result."
            ),
        }

    combined = f"{stderr}\n{stdout}"
    missing = _MISSING_MODULE_RE.search(combined)
    if missing is not None:
        module = missing.group(1).split(".", 1)[0]
        return {
            "error_class": "missing_library",
            "retryable": True,
            "suggested_next": (
                f"Module {module!r} was not installed. Re-run run_python with the "
                f"providing distribution added to libs (import name and PyPI name "
                f"often differ, e.g. import fitz → pymupdf)."
            ),
        }
    exception = _TRACEBACK_LAST_RE.search(combined)
    if exception is not None:
        return {
            "error_class": "python_error",
            "retryable": True,
            "suggested_next": (
                f"The script raised {exception.group(1)}. Fix the script logic or "
                "inspect the inputs with inspect_workspace before retrying."
            ),
        }
    return {
        "error_class": "execution_failed",
        "retryable": True,
        "suggested_next": (
            "The interpreter could not complete the script. Check the stderr text "
            "and simplify the approach."
        ),
    }


def run_python(
    arguments: dict[str, Any],
    *,
    workspace: RunWorkspace,
    settings: Any,
    label: str = "action",
) -> dict[str, Any]:
    """Execute a model-authored script via ``uvx --with <libs> python``."""
    script = arguments.get("script")
    if script is None:
        script = arguments.get("code") or arguments.get("source")
    body = str(script or "")
    if not body.strip():
        return {
            "ok": False,
            "tool": RUN_PYTHON_ACTION,
            "error": "script is required",
            "error_class": "invalid_action",
            "retryable": True,
            "suggested_next": "Provide the Python source to execute in `script`.",
        }

    libs, lib_error = validate_libs(
        arguments.get("libs") or arguments.get("with_packages"), settings=settings
    )
    if lib_error is not None:
        return {
            "ok": False,
            "tool": RUN_PYTHON_ACTION,
            "error": lib_error,
            "error_class": "invalid_action",
            "retryable": True,
            "suggested_next": "Correct the libs list and retry.",
        }

    script_path = workspace.next_script_path(label)
    script_path.write_text(body, encoding="utf-8")
    relative_script = workspace.relative_of(script_path)

    baseline = workspace.snapshot()
    timeout = float(getattr(settings, "cli_tools_timeout_seconds", 120) or 120)
    limit = _observation_limit(settings)

    try:
        result = run_uvx(
            PYTHON_ENTRYPOINT,
            [relative_script],
            cwd=str(workspace.root),
            with_packages=libs,
            timeout_seconds=timeout,
        )
    except UvxRunnerError as exc:
        return {
            "ok": False,
            "tool": RUN_PYTHON_ACTION,
            "libs": libs,
            "script_path": relative_script,
            "error": str(exc),
            "error_class": "runner_unavailable",
            "retryable": False,
            "suggested_next": "uvx is unavailable; the step cannot proceed.",
        }

    produced = [
        path
        for path in workspace.files_since(baseline)
        if path.resolve() != script_path.resolve()
    ]
    ok = bool(getattr(result, "ok", False))
    stdout = str(getattr(result, "stdout", "") or "")
    stderr = str(getattr(result, "stderr", "") or "")
    insight = classify_python_result(
        ok=ok, stdout=stdout, stderr=stderr, produced=produced
    )

    payload: dict[str, Any] = {
        "ok": ok,
        "tool": RUN_PYTHON_ACTION,
        "libs": libs,
        "script_path": relative_script,
        "exit_code": getattr(result, "exit_code", None),
        "stdout": _clip(stdout, limit),
        "stderr": _clip(stderr, limit),
        "output_files": [str(p) for p in produced],
        "produced_relative": [workspace.relative_of(p) for p in produced],
        **insight,
    }
    if produced:
        payload["output_file"] = str(produced[0])
    if not ok and not payload.get("error"):
        payload["error"] = stderr.strip() or "python script failed"
    logger.info(
        "run_python ok=%s libs=%s produced=%d exit=%s",
        ok,
        libs,
        len(produced),
        payload.get("exit_code"),
    )
    return payload


def run_cli(
    arguments: dict[str, Any],
    *,
    workspace: RunWorkspace,
    settings: Any,
    attachments: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute a PyPI console script via uvx, confined to the workspace."""
    from api.app.agent.uvx_invoke import (
        classify_uvx_tool_result,
        preflight_uvx_tool_args,
        remediate_uvx_tool_args,
    )

    args, preflight_error = preflight_uvx_tool_args(
        dict(arguments or {}), prior_attempts=None, attachments=attachments
    )
    limit = _observation_limit(settings)
    if preflight_error is not None:
        payload = {**preflight_error, "tool": RUN_CLI_ACTION}
        payload.update(classify_uvx_tool_result(payload))
        return payload

    baseline = workspace.snapshot()

    def _invoke(invocation: dict[str, Any]) -> Any:
        raw_list = invocation.get("args_list") or []
        if isinstance(raw_list, str):
            raw_list = [raw_list]
        with_packages = invocation.get("with_packages") or invocation.get("with") or []
        if isinstance(with_packages, str):
            with_packages = [with_packages]
        from_spec = invocation.get("from_spec") or invocation.get("from")
        return run_uvx(
            str(invocation.get("package") or "").strip(),
            [str(x).replace("\\", "/") for x in list(raw_list)],
            cwd=str(workspace.root),
            help_only=bool(invocation.get("help_only") or invocation.get("help")),
            from_spec=str(from_spec).strip() if from_spec else None,
            with_packages=list(with_packages),
            timeout_seconds=float(
                getattr(settings, "cli_tools_timeout_seconds", 120) or 120
            ),
        )

    notes: list[str] = list(args.get("preflight_notes") or [])
    try:
        result = _invoke(args)
    except UvxRunnerError as exc:
        payload = {
            "ok": False,
            "tool": RUN_CLI_ACTION,
            "package": args.get("package"),
            "error": str(exc),
        }
        payload.update(classify_uvx_tool_result(payload))
        return payload

    # One correction pass: uvx reports the real executable when the install
    # name differs, which is a mechanical fix rather than a strategy change.
    if not getattr(result, "ok", False):
        corrected = remediate_uvx_tool_args(
            args, str(getattr(result, "stderr", "") or "")
        )
        if corrected is not None:
            notes.append("applied uvx stderr remediation")
            try:
                result = _invoke(corrected)
                args = corrected
            except UvxRunnerError as exc:
                payload = {
                    "ok": False,
                    "tool": RUN_CLI_ACTION,
                    "package": corrected.get("package"),
                    "error": str(exc),
                }
                payload.update(classify_uvx_tool_result(payload))
                return payload

    produced = workspace.files_since(baseline)
    payload = {
        "ok": bool(getattr(result, "ok", False)),
        "tool": RUN_CLI_ACTION,
        "package": getattr(result, "package", args.get("package")),
        "from_spec": args.get("from_spec"),
        "with_packages": list(args.get("with_packages") or []),
        "args_list": list(getattr(result, "args_list", args.get("args_list") or [])),
        "help_only": bool(args.get("help_only") or args.get("help")),
        "exit_code": getattr(result, "exit_code", None),
        "stdout": _clip(getattr(result, "stdout", ""), limit),
        "stderr": _clip(getattr(result, "stderr", ""), limit),
        "output_files": [str(p) for p in produced],
        "produced_relative": [workspace.relative_of(p) for p in produced],
    }
    if produced:
        payload["output_file"] = str(produced[0])
    if notes:
        payload["preflight_notes"] = notes
        payload["preflight_corrected"] = True
    error = getattr(result, "error", None)
    if error and not payload["ok"]:
        payload["error"] = str(error)
    payload.update(classify_uvx_tool_result(payload))
    return payload


def inspect_workspace(
    arguments: dict[str, Any],
    *,
    workspace: RunWorkspace,
    settings: Any,
) -> dict[str, Any]:
    """List workspace files and optionally peek inside them."""
    limit = _observation_limit(settings)
    listing = workspace.listing()
    requested = arguments.get("paths") or []
    if isinstance(requested, str):
        requested = [requested]

    peeks: list[dict[str, Any]] = []
    peek_bytes = max(0, min(int(arguments.get("peek_bytes") or 2000), limit))
    for raw in list(requested)[:5]:
        resolved = workspace.resolve_within(str(raw))
        if resolved is None or not resolved.is_file():
            peeks.append({"path": str(raw), "error": "not found in workspace"})
            continue
        entry: dict[str, Any] = {
            "path": workspace.relative_of(resolved),
            "bytes": resolved.stat().st_size,
        }
        if peek_bytes and resolved.suffix.lower() in _PEEK_TEXT_SUFFIXES:
            try:
                entry["head"] = resolved.read_text(
                    encoding="utf-8", errors="replace"
                )[:peek_bytes]
            except OSError as exc:
                entry["error"] = str(exc)
        peeks.append(entry)

    return {
        "ok": True,
        "tool": INSPECT_ACTION,
        "probe": True,
        "entries": listing,
        "peeks": peeks,
        "error_class": "inspection",
        "retryable": True,
        "suggested_next": (
            "Inspection does not satisfy a goal. Use run_python or run_uvx to act."
        ),
    }
