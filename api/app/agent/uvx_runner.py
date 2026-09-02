"""Real ``uvx`` / ``uv tool run`` subprocess helper (Astral uv).

Never stubs the installer — always shells out to the host ``uvx`` or ``uv`` binary.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from api.app.logging_config import get_logger
from api.app.settings import get_settings

logger = get_logger("api.agent.uvx_runner")

_SAFE_PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_UNSAFE_ARG = re.compile(r"[;&|`$<>\\\n\r]")
_OUTPUT_FLAGS = frozenset(
    {"-o", "--output", "--out", "-out", "--output-file", "--outfile", "-f", "--file"}
)
_OUTPUT_DIR_FLAGS = frozenset({"--output-dir", "-d", "--outdir"})


class UvxRunnerError(Exception):
    """Raised when uvx cannot be invoked safely."""

    def __init__(self, message: str, *, code: str = "uvx_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class UvxResult:
    ok: bool
    exit_code: int | None
    stdout: str
    stderr: str
    package: str
    args_list: list[str]
    cmd: list[str]
    error: str | None = None
    output_file: str | None = None
    output_files: tuple[str, ...] = ()
    with_packages: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "package": self.package,
            "args_list": list(self.args_list),
            "cmd": list(self.cmd),
        }
        if self.error:
            payload["error"] = self.error
        if self.with_packages:
            payload["with_packages"] = list(self.with_packages)
        if self.output_file:
            payload["output_file"] = self.output_file
            payload.setdefault("path", self.output_file)
        if self.output_files:
            payload["output_files"] = list(self.output_files)
            if not self.output_file:
                payload["output_file"] = self.output_files[0]
                payload.setdefault("path", self.output_files[0])
        return payload


def infer_output_dir_from_args(
    args_list: Sequence[str],
    *,
    cwd: str | Path | None = None,
) -> Path | None:
    """Return a declared output directory from common CLI flags, if any."""
    args = [str(x) for x in args_list]
    idx = 0
    while idx < len(args):
        token = args[idx]
        for flag in _OUTPUT_DIR_FLAGS:
            if token == flag:
                if idx + 1 < len(args):
                    raw = args[idx + 1].strip()
                    if raw:
                        path = Path(raw)
                        if not path.is_absolute() and cwd:
                            path = Path(cwd) / path
                        return path.resolve()
                return None
            prefix = f"{flag}="
            if token.startswith(prefix):
                raw = token[len(prefix) :].strip()
                if raw:
                    path = Path(raw)
                    if not path.is_absolute() and cwd:
                        path = Path(cwd) / path
                    return path.resolve()
        idx += 1
    return None


def infer_output_path_from_args(args_list: Sequence[str]) -> str | None:
    """Return a declared output path from common CLI output flags, if any."""
    args = [str(x) for x in args_list]
    idx = 0
    while idx < len(args):
        token = args[idx]
        for flag in _OUTPUT_FLAGS:
            if token == flag:
                if idx + 1 < len(args):
                    return args[idx + 1]
                return None
            prefix = f"{flag}="
            if token.startswith(prefix):
                value = token[len(prefix) :].strip()
                return value or None
        idx += 1
    return None


def _input_basenames(args_list: Sequence[str]) -> set[str]:
    names: set[str] = set()
    for raw in args_list:
        token = str(raw).strip()
        if not token or token.startswith("-"):
            continue
        path = Path(token)
        if path.suffix:
            names.add(path.name)
    return names


def _snapshot_dir_files(dirpath: Path) -> dict[str, float]:
    if not dirpath.is_dir():
        return {}
    snapshot: dict[str, float] = {}
    for entry in dirpath.iterdir():
        if entry.is_file():
            snapshot[entry.name] = entry.stat().st_mtime
    return snapshot


def _resolve_output_candidate(raw: str | None, *, cwd: str | Path | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    path = Path(str(raw).strip())
    if not path.is_absolute() and cwd:
        path = Path(cwd) / path
    resolved = path.resolve()
    return str(resolved) if resolved.is_file() else None


def _detect_new_output_files(
    *,
    cwd: str | Path | None,
    before: dict[str, float],
    args_list: Sequence[str],
    scan_root: Path | None = None,
) -> list[str]:
    root = scan_root
    if root is None:
        if cwd is None:
            return []
        root = Path(cwd)
    if not root.is_dir():
        return []
    inputs = _input_basenames(args_list)
    after = _snapshot_dir_files(root)
    changed: list[str] = []
    for name, mtime in after.items():
        if name in inputs:
            continue
        if name not in before or mtime > before.get(name, 0.0) + 1e-6:
            changed.append(name)
    return [str((root / name).resolve()) for name in sorted(changed)]


def resolve_output_files(
    *,
    args_list: Sequence[str],
    cwd: str | Path | None,
    ok: bool,
    help_only: bool,
    before_snapshot: dict[str, float] | None = None,
    output_dir_snapshot: dict[str, float] | None = None,
    scan_root: Path | None = None,
) -> list[str]:
    """Best-effort output paths after a successful CLI run."""
    if not ok or help_only:
        return []
    declared = infer_output_path_from_args(args_list)
    resolved = _resolve_output_candidate(declared, cwd=cwd)
    if resolved:
        return [resolved]
    snapshot = output_dir_snapshot if scan_root is not None else before_snapshot
    if snapshot is not None:
        return _detect_new_output_files(
            cwd=cwd,
            before=snapshot,
            args_list=args_list,
            scan_root=scan_root,
        )
    return []


def resolve_output_file(
    *,
    args_list: Sequence[str],
    cwd: str | Path | None,
    ok: bool,
    help_only: bool,
    before_snapshot: dict[str, float] | None = None,
    output_dir_snapshot: dict[str, float] | None = None,
    scan_root: Path | None = None,
) -> str | None:
    """Best-effort single output path after a successful CLI run."""
    files = resolve_output_files(
        args_list=args_list,
        cwd=cwd,
        ok=ok,
        help_only=help_only,
        before_snapshot=before_snapshot,
        output_dir_snapshot=output_dir_snapshot,
        scan_root=scan_root,
    )
    if len(files) == 1:
        return files[0]
    if len(files) > 1:
        return files[0]
    return None


def resolve_uvx_prefix() -> list[str] | None:
    """Return argv prefix for real uvx, or None if uv/uvx is missing."""
    if shutil.which("uvx"):
        return ["uvx"]
    uv = shutil.which("uv")
    if uv:
        return [uv, "tool", "run"]
    return None


def _validate_package(package: str) -> str:
    name = (package or "").strip()
    if not name or not _SAFE_PACKAGE.match(name):
        raise UvxRunnerError(
            f"invalid uvx package name: {package!r}",
            code="invalid_package",
        )
    return name


def _validate_with_packages(with_packages: Sequence[str] | None) -> list[str]:
    out: list[str] = []
    for raw in with_packages or []:
        name = str(raw).strip()
        if not name:
            continue
        out.append(_validate_package(name))
    return out


def _build_uvx_cmd(
    prefix: list[str],
    *,
    package: str,
    args: list[str],
    from_spec: str | None,
    with_packages: Sequence[str],
) -> list[str]:
    cmd = list(prefix)
    if from_spec:
        cmd.extend(["--from", from_spec])
    for dep in with_packages:
        cmd.extend(["--with", dep])
    cmd.extend([package, *args])
    return cmd


def _validate_args(args_list: Sequence[str]) -> list[str]:
    out: list[str] = []
    for raw in args_list:
        token = str(raw)
        if not token:
            raise UvxRunnerError("empty uvx argument", code="invalid_args")
        if _UNSAFE_ARG.search(token):
            raise UvxRunnerError(
                f"unsafe character in uvx arg: {token!r}",
                code="invalid_args",
            )
        out.append(token)
    return out


def run_uvx(
    package: str,
    args_list: Sequence[str] | None = None,
    *,
    cwd: str | Path | None = None,
    timeout_seconds: float | None = None,
    max_output_bytes: int | None = None,
    help_only: bool = False,
    from_spec: str | None = None,
    with_packages: Sequence[str] | None = None,
) -> UvxResult:
    """Install-and-run ``package`` via real ``uvx`` / ``uv tool run``.

    When ``from_spec`` is set (e.g. ``markitdown[pdf]``), runs:
    ``uvx --from <from_spec> <package> …``.
    When ``with_packages`` is set, each entry is passed as ``--with <dep>``.
    When ``package`` itself contains extras like ``markitdown[pdf]``, it is
    treated as ``from_spec`` and the console script defaults to the base name.
    """
    settings = get_settings()
    if not settings.cli_tools_enabled:
        raise UvxRunnerError("CLI tool execution is disabled", code="cli_disabled")

    raw_package = (package or "").strip()
    raw_from = (from_spec or "").strip() or None
    entry = raw_package
    if "[" in raw_package and "]" in raw_package and raw_from is None:
        raw_from = raw_package
        entry = raw_package.split("[", 1)[0].strip()
    pkg = _validate_package(entry)
    if raw_from is not None:
        # allow extras: name[extra,...]
        base = raw_from.split("[", 1)[0].strip()
        _validate_package(base)
        if "[" in raw_from and not re.match(
            r"^[A-Za-z0-9][A-Za-z0-9._+-]*(\[[A-Za-z0-9][A-Za-z0-9._,+-]*\])?$",
            raw_from,
        ):
            raise UvxRunnerError(
                f"invalid uvx from_spec: {raw_from!r}",
                code="invalid_package",
            )
    args = _validate_args(list(args_list or []))
    if help_only and "--help" not in args:
        args = [*args, "--help"]
    deps = _validate_with_packages(with_packages)

    prefix = resolve_uvx_prefix()
    if prefix is None:
        raise UvxRunnerError(
            "uvx/uv not found on PATH; install Astral uv",
            code="uvx_missing",
        )

    cmd = _build_uvx_cmd(
        prefix,
        package=pkg,
        args=args,
        from_spec=raw_from,
        with_packages=deps,
    )
    timeout = float(
        timeout_seconds
        if timeout_seconds is not None
        else settings.cli_tools_timeout_seconds
    )
    max_bytes = int(
        max_output_bytes
        if max_output_bytes is not None
        else settings.cli_tools_max_output_bytes
    )
    workdir = str(cwd) if cwd is not None else None
    output_dir = (
        infer_output_dir_from_args(args, cwd=workdir) if workdir and not help_only else None
    )
    before_files = (
        _snapshot_dir_files(Path(workdir)) if workdir and not help_only else {}
    )
    before_output_dir: dict[str, float] = {}
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        before_output_dir = _snapshot_dir_files(output_dir)

    logger.info("uvx_exec cmd=%s cwd=%s", cmd, workdir)
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
        )
    except FileNotFoundError as exc:
        raise UvxRunnerError(
            f"uvx binary not found: {exc}",
            code="uvx_missing",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        return UvxResult(
            ok=False,
            exit_code=None,
            stdout=(exc.stdout or "")[:max_bytes] if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "")[:2000] if isinstance(exc.stderr, str) else "",
            package=pkg,
            args_list=args,
            cmd=cmd,
            error=f"uvx timed out after {timeout}s",
        )

    stdout = (completed.stdout or "")[:max_bytes]
    stderr = (completed.stderr or "")[:2000]
    ok = completed.returncode == 0
    error = None if ok else (stderr.strip() or f"exit code {completed.returncode}")
    output_files = resolve_output_files(
        args_list=args,
        cwd=workdir,
        ok=ok,
        help_only=help_only,
        before_snapshot=before_files or None,
        output_dir_snapshot=before_output_dir or None,
        scan_root=output_dir,
    )
    if not output_files and before_files:
        output_files = resolve_output_files(
            args_list=args,
            cwd=workdir,
            ok=ok,
            help_only=help_only,
            before_snapshot=before_files or None,
        )
    output_file = output_files[0] if len(output_files) == 1 else (
        output_files[0] if output_files else None
    )
    return UvxResult(
        ok=ok,
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        package=pkg,
        args_list=args,
        cmd=cmd,
        error=error,
        output_file=output_file,
        output_files=tuple(output_files),
        with_packages=tuple(deps),
    )


def run_uvx_from_arguments(
    arguments: dict[str, Any] | None,
    *,
    prior_attempts: Sequence[dict[str, Any]] | None = None,
    attachments: Sequence[dict[str, Any]] | None = None,
    instruction: str = "",
    success_criteria: str = "",
    use_recovery: bool = True,
) -> dict[str, Any]:
    """Tool-facing wrapper: map LLM/tool args onto ``run_uvx``."""
    if use_recovery:
        from api.app.agent.uvx_invoke import run_uvx_with_recovery

        return run_uvx_with_recovery(
            dict(arguments or {}),
            prior_attempts=prior_attempts,
            attachments=attachments,
            instruction=instruction,
            success_criteria=success_criteria,
        )

    args = dict(arguments or {})
    package = str(args.get("package") or "").strip()
    raw_list = args.get("args_list") or args.get("args") or []
    if isinstance(raw_list, str):
        raw_list = [raw_list]
    raw_list = [str(x).replace(chr(92), "/") for x in list(raw_list)]
    cwd = args.get("cwd") or args.get("working_dir")
    help_only = bool(args.get("help_only") or args.get("help"))
    from_spec = args.get("from_spec") or args.get("from")
    raw_with = args.get("with_packages") or args.get("with") or []
    if isinstance(raw_with, str):
        raw_with = [raw_with]
    with_packages = [str(x).strip() for x in list(raw_with) if str(x).strip()]
    try:
        result = run_uvx(
            package,
            list(raw_list),
            cwd=cwd,
            help_only=help_only,
            from_spec=str(from_spec).strip() if from_spec else None,
            with_packages=with_packages,
        )
    except UvxRunnerError as exc:
        return {
            "ok": False,
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
            "package": package,
            "args_list": list(raw_list) if isinstance(raw_list, list) else [],
            "error": str(exc),
            "code": exc.code,
        }
    return result.as_dict()
