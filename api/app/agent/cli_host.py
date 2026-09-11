"""Host OS CLI readiness — check and optional install (control plane).

Used by admin/ops endpoints only. The Deep Agents harness does not call
this; it only runs tools that are already present on PATH when needed.
"""

from __future__ import annotations

import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from api.app.logging_config import get_logger

logger = get_logger("api.agent.cli_host")

_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_UNSAFE_CHARS = re.compile(r"[;&|`$<>\\\n\r]")

_ALLOWED_INSTALLERS = frozenset(
    {
        "winget",
        "choco",
        "scoop",
        "brew",
        "apt-get",
        "apt",
        "dnf",
        "yum",
        "pacman",
        "zypper",
        "pip",
        "pipx",
        "python",
        "python3",
        "py",
        "npm",
        "npx",
        "cargo",
    }
)


class CliHostError(Exception):
    """Raised when a check/install request cannot proceed."""

    def __init__(self, message: str, *, code: str = "cli_host_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CliCheckResult:
    tool_name: str
    command: str
    installed: bool
    resolved_path: str | None
    platform: str


@dataclass(frozen=True)
class CliInstallResult:
    tool_name: str
    command: str
    ok: bool
    installed: bool
    install_cmd: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    resolved_path: str | None
    platform: str
    error: str | None = None


def host_platform() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "darwin"
    if system.startswith("linux"):
        return "linux"
    return system or "unknown"


def _path_key(entry: str) -> str:
    """Normalize a PATH entry for de-duplication (case-insensitive on Windows)."""
    expanded = os.path.expandvars(os.path.expanduser(entry.strip().strip('"')))
    if not expanded:
        return ""
    try:
        return os.path.normcase(os.path.abspath(expanded))
    except (OSError, ValueError):
        return os.path.normcase(expanded)


def _merge_path_entries(*chunks: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        if not chunk:
            continue
        for part in chunk.split(os.pathsep):
            raw = part.strip().strip('"')
            if not raw:
                continue
            key = _path_key(raw)
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(os.path.expandvars(os.path.expanduser(raw)))
    return ordered


def _windows_registry_path() -> str:
    """Machine + user PATH from the registry (not the stale process env)."""
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return ""
    values: list[str] = []
    for root, subkey in (
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, "Environment"),
    ):
        try:
            with winreg.OpenKey(root, subkey) as key:
                raw, typ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        text = str(raw or "")
        if typ == getattr(winreg, "REG_EXPAND_SZ", 2):
            text = os.path.expandvars(text)
        if text:
            values.append(text)
    return os.pathsep.join(values)


def _windows_common_bin_dirs() -> list[str]:
    """Extra dirs installers often use without updating this process PATH yet."""
    dirs: list[str] = []
    choco = os.environ.get("ChocolateyInstall") or r"C:\ProgramData\chocolatey"
    dirs.append(os.path.join(choco, "bin"))
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        root = os.environ.get(env_name)
        if not root or not os.path.isdir(root):
            continue
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for name in names:
            if name.lower().startswith("imagemagick"):
                dirs.append(os.path.join(root, name))
    scoop = os.path.join(os.path.expanduser("~"), "scoop", "shims")
    dirs.append(scoop)
    return dirs


def _posix_login_path(*, timeout_seconds: float = 5.0) -> str:
    """PATH from a login shell (picks up brew/apt profile updates)."""
    candidates: list[str] = []
    shell = (os.environ.get("SHELL") or "").strip()
    if shell:
        candidates.append(shell)
    candidates.extend(["/bin/zsh", "/bin/bash", "/bin/sh"])
    seen: set[str] = set()
    for shell_path in candidates:
        if not shell_path or shell_path in seen:
            continue
        seen.add(shell_path)
        if not os.path.isfile(shell_path):
            continue
        try:
            proc = subprocess.run(
                [shell_path, "-l", "-c", 'printf %s "$PATH"'],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        out = (proc.stdout or "").strip()
        if proc.returncode == 0 and out:
            return out
    return ""


def _posix_common_bin_dirs() -> list[str]:
    home = os.path.expanduser("~")
    return [
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/usr/local/bin",
        "/usr/local/sbin",
        os.path.join(home, ".local", "bin"),
        os.path.join(home, ".cargo", "bin"),
        "/home/linuxbrew/.linuxbrew/bin",
    ]


def refresh_process_path(*, include_login_shell: bool = False) -> str:
    """Reload PATH into this process from OS sources (cross-platform).

    Installers often update the machine/user environment, but a long-lived API
    process keeps a stale PATH. Call this after install (and optionally on check)
    so ``shutil.which`` can see newly installed binaries.
    """
    plat = host_platform()
    current = os.environ.get("PATH", "")
    extras: list[str] = []

    if plat == "windows":
        registry = _windows_registry_path()
        extras.extend(_windows_common_bin_dirs())
        merged = _merge_path_entries(registry, current, *extras)
    else:
        login = _posix_login_path() if include_login_shell else ""
        extras.extend(_posix_common_bin_dirs())
        merged = _merge_path_entries(login, current, *extras)

    new_path = os.pathsep.join(merged)
    os.environ["PATH"] = new_path
    logger.debug(
        "cli_host_path_refreshed platform=%s entries=%s login_shell=%s",
        plat,
        len(merged),
        include_login_shell,
    )
    return new_path


def resolve_command_path(
    command: str,
    *,
    refresh: bool = False,
    include_login_shell: bool = False,
) -> str | None:
    """Resolve a command on PATH, optionally refreshing env first.

    Also checks common installer directories directly so tools like ImageMagick
    are found even when PATH updates have not fully propagated.
    """
    if refresh:
        refresh_process_path(include_login_shell=include_login_shell)
    found = shutil.which(command)
    if found:
        return found

    plat = host_platform()
    dirs = _windows_common_bin_dirs() if plat == "windows" else _posix_common_bin_dirs()
    names = [command]
    if plat == "windows":
        names.extend([f"{command}.exe", f"{command}.cmd", f"{command}.bat"])
    for directory in dirs:
        for name in names:
            candidate = os.path.join(directory, name)
            try:
                if os.path.isfile(candidate) and (
                    plat == "windows" or os.access(candidate, os.X_OK)
                ):
                    return candidate
            except OSError:
                continue
    return None


def command_from_config(config: dict[str, Any] | None) -> str:
    """Return the host binary name from a tool_registry CLI config."""
    if not isinstance(config, dict):
        raise CliHostError("CLI tool has no config.command", code="missing_command")
    raw = str(config.get("command") or "").strip()
    if not raw:
        raise CliHostError("CLI tool has no config.command", code="missing_command")
    # Reject path-like commands for host install/check targets.
    if "/" in raw or "\\" in raw:
        raise CliHostError(
            "config.command must be a bare executable name (not a path)",
            code="invalid_command",
        )
    token = raw.split()[0]
    if not _SAFE_TOKEN.match(token):
        raise CliHostError(
            f"unsafe command name: {token!r}",
            code="invalid_command",
        )
    return token


def package_from_config(config: dict[str, Any] | None, *, command: str) -> str:
    if isinstance(config, dict):
        pkg = str(config.get("package") or "").strip()
        if pkg:
            if not _SAFE_TOKEN.match(pkg):
                raise CliHostError(
                    f"unsafe package name: {pkg!r}",
                    code="invalid_package",
                )
            return pkg
    return command


def has_install_spec(config: dict[str, Any] | None) -> bool:
    if not isinstance(config, dict):
        return False
    if config.get("install") is not None:
        return True
    if config.get("install_command") is not None:
        return True
    return False


def check_cli_installed(*, tool_name: str, config: dict[str, Any] | None) -> CliCheckResult:
    command = command_from_config(config)
    # Cheap refresh so post-install PATH / common bins are visible without API restart.
    resolved = resolve_command_path(command, refresh=True, include_login_shell=False)
    return CliCheckResult(
        tool_name=tool_name,
        command=command,
        installed=resolved is not None,
        resolved_path=resolved,
        platform=host_platform(),
    )


def _validate_install_argv(argv: list[str]) -> list[str]:
    if not argv:
        raise CliHostError("empty install command", code="invalid_install")
    cleaned: list[str] = []
    for i, raw in enumerate(argv):
        token = str(raw).strip()
        if not token:
            raise CliHostError("empty install argument", code="invalid_install")
        if _UNSAFE_CHARS.search(token):
            raise CliHostError(
                f"unsafe character in install arg: {token!r}",
                code="invalid_install",
            )
        if i == 0:
            base = token.lower().removesuffix(".exe")
            if base not in _ALLOWED_INSTALLERS:
                raise CliHostError(
                    f"installer not allowed: {token!r}",
                    code="installer_not_allowed",
                )
        cleaned.append(token)

    # python -m pip install … must stay on that shape
    head = cleaned[0].lower().removesuffix(".exe")
    if head in {"python", "python3", "py"}:
        if len(cleaned) < 4 or cleaned[1] != "-m" or cleaned[2] not in {"pip", "pipx"}:
            raise CliHostError(
                "python install must be: python -m pip|pipx …",
                code="invalid_install",
            )
    return cleaned


def _argv_from_string(raw: str) -> list[str]:
    try:
        parts = shlex.split(raw, posix=os_name_is_posix())
    except ValueError as exc:
        raise CliHostError(f"could not parse install_command: {exc}", code="invalid_install") from exc
    return _validate_install_argv(parts)


def os_name_is_posix() -> bool:
    return sys.platform != "win32"


def _default_install_argv(*, package: str, plat: str) -> list[str]:
    """Best-effort package-manager guess when config has no install spec."""
    if plat == "windows":
        if shutil.which("winget"):
            return _validate_install_argv(
                ["winget", "install", "-e", "--id", package, "--accept-package-agreements", "--accept-source-agreements"]
            )
        if shutil.which("choco"):
            return _validate_install_argv(["choco", "install", package, "-y"])
        if shutil.which("scoop"):
            return _validate_install_argv(["scoop", "install", package])
        raise CliHostError(
            "no supported Windows package manager found (winget/choco/scoop); "
            "set config.install on the tool",
            code="no_installer",
        )
    if plat == "darwin":
        if shutil.which("brew"):
            return _validate_install_argv(["brew", "install", package])
        raise CliHostError(
            "Homebrew (brew) not found; set config.install on the tool",
            code="no_installer",
        )
    if plat == "linux":
        if shutil.which("apt-get"):
            return _validate_install_argv(["apt-get", "install", "-y", package])
        if shutil.which("apt"):
            return _validate_install_argv(["apt", "install", "-y", package])
        if shutil.which("dnf"):
            return _validate_install_argv(["dnf", "install", "-y", package])
        if shutil.which("yum"):
            return _validate_install_argv(["yum", "install", "-y", package])
        raise CliHostError(
            "no supported Linux package manager found; set config.install on the tool",
            code="no_installer",
        )
    raise CliHostError(f"unsupported platform for default install: {plat}", code="no_installer")


def resolve_install_argv(config: dict[str, Any] | None) -> list[str]:
    """Resolve install argv from config or platform defaults."""
    command = command_from_config(config)
    package = package_from_config(config, command=command)
    plat = host_platform()
    assert isinstance(config, dict)

    install = config.get("install")
    if isinstance(install, list):
        return _validate_install_argv([str(x) for x in install])
    if isinstance(install, str):
        return _argv_from_string(install)
    if isinstance(install, dict):
        # Prefer exact platform, then common aliases
        candidates = [plat]
        if plat == "windows":
            candidates.extend(["win", "win32"])
        elif plat == "darwin":
            candidates.extend(["macos", "osx", "mac"])
        elif plat == "linux":
            candidates.append("unix")
        for key in candidates:
            raw = install.get(key)
            if raw is None:
                continue
            if isinstance(raw, list):
                return _validate_install_argv([str(x) for x in raw])
            if isinstance(raw, str):
                return _argv_from_string(raw)
        raise CliHostError(
            f"config.install has no entry for platform {plat!r}",
            code="missing_install_platform",
        )

    raw_cmd = config.get("install_command")
    if isinstance(raw_cmd, str) and raw_cmd.strip():
        return _argv_from_string(raw_cmd)
    if isinstance(raw_cmd, list):
        return _validate_install_argv([str(x) for x in raw_cmd])

    return _default_install_argv(package=package, plat=plat)


def install_cli_tool(
    *,
    tool_name: str,
    config: dict[str, Any] | None,
    timeout_seconds: int,
    max_output_bytes: int,
) -> CliInstallResult:
    """Attempt to install a registered CLI tool on the host OS."""
    plat = host_platform()
    command = command_from_config(config)
    before = shutil.which(command)
    if before:
        return CliInstallResult(
            tool_name=tool_name,
            command=command,
            ok=True,
            installed=True,
            install_cmd=[],
            exit_code=None,
            stdout="",
            stderr="",
            resolved_path=before,
            platform=plat,
            error=None,
        )

    argv = resolve_install_argv(config)
    logger.info(
        "cli_host_install_start tool=%s cmd=%s",
        tool_name,
        argv,
    )
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except FileNotFoundError:
        return CliInstallResult(
            tool_name=tool_name,
            command=command,
            ok=False,
            installed=False,
            install_cmd=argv,
            exit_code=None,
            stdout="",
            stderr="",
            resolved_path=None,
            platform=plat,
            error=f"installer not found: {argv[0]!r}",
        )
    except subprocess.TimeoutExpired:
        return CliInstallResult(
            tool_name=tool_name,
            command=command,
            ok=False,
            installed=False,
            install_cmd=argv,
            exit_code=None,
            stdout="",
            stderr="",
            resolved_path=None,
            platform=plat,
            error=f"install timed out after {timeout_seconds}s",
        )

    stdout = (proc.stdout or "")[:max_output_bytes]
    stderr = (proc.stderr or "")[:max_output_bytes]
    # Installers update machine PATH; re-read OS env before which().
    after = resolve_command_path(command, refresh=True, include_login_shell=True)
    ok = proc.returncode == 0 and after is not None
    error = None
    if proc.returncode != 0:
        error = stderr.strip() or f"exit code {proc.returncode}"
    elif after is None:
        error = (
            "installer exited 0 but command still not on PATH; "
            "open a new shell or set config.package / config.install"
        )

    logger.info(
        "cli_host_install_done tool=%s ok=%s exit=%s path=%s",
        tool_name,
        ok,
        proc.returncode,
        after,
    )
    return CliInstallResult(
        tool_name=tool_name,
        command=command,
        ok=ok,
        installed=after is not None,
        install_cmd=argv,
        exit_code=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        resolved_path=after,
        platform=plat,
        error=error,
    )
