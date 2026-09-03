"""Preflight, remediation, and help-ladder orchestration for ``run_uvx`` invocations."""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any, Sequence

from api.app.agent.outcome_verifier import is_probe_attempt
from api.app.agent.uvx_runner import UvxRunnerError, run_uvx

_EXECUTABLE_NOT_PROVIDED_RE = re.compile(
    r"executable named [`']([^`']+)[`'] is not provided by package [`']([^`']+)[`']",
    re.IGNORECASE,
)
_UVX_USE_INSTEAD_RE = re.compile(
    r"Use [`']uvx --from\s+(\S+)\s+(\S+)[`'] instead",
    re.IGNORECASE,
)
_AVAILABLE_EXECUTABLE_RE = re.compile(
    r"The following executables are available:\s*\n-\s*(\S+)",
    re.IGNORECASE,
)
_CLI_COMMAND_RE = re.compile(r"^\s{2,}(\S+)\s{2,}.+$", re.MULTILINE)
_OPTION_SECTION_RE = re.compile(r"^(Options|Optional arguments|Optional Arguments|Flags):\s*$", re.I)
_SECTION_STOP_RE = re.compile(
    r"^(Commands|Arguments|Positional arguments|Usage|Examples):\s*$",
    re.I,
)
_FLAG_TOKEN_RE = re.compile(r"(?<![\w-])(--[a-zA-Z][\w-]*|-[a-zA-Z])\b")
_COMMAND_NAME_RE = re.compile(r"^[a-zA-Z][\w-]*$")
_GOAL_SUBCOMMAND_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsplit\b", re.I), "split"),
    (re.compile(r"\bmerge\b", re.I), "merge"),
    (re.compile(r"\bconvert|transcode|export\b", re.I), "transcode"),
    (re.compile(r"\bdiff|compare\b", re.I), "diff"),
    (re.compile(r"\bview|inspect|preview|readable\b", re.I), "view"),
)
# CLI families that use optional format plugins via uvx --with (edge registry).
_CLI_PLUGIN_FAMILIES: dict[str, dict[str, tuple[str, ...]]] = {
    "pyexcel": {
        ".xlsx": ("pyexcel-xlsx",),
        ".xls": ("pyexcel-xls",),
        ".ods": ("pyexcel-ods",),
    },
}


def _install_base_name(raw: str) -> str:
    return raw.split("[", 1)[0].strip().lower()


def resolve_cli_plugin_family(
    package: str,
    from_spec: str | None = None,
) -> str | None:
    """Return a registered plugin family when package/from_spec belong to it."""
    names = [
        _install_base_name(str(raw))
        for raw in (package, from_spec or "")
        if str(raw or "").strip()
    ]
    for family_id in _CLI_PLUGIN_FAMILIES:
        for name in names:
            if name == family_id or name.startswith(f"{family_id}-"):
                return family_id
    return None


def normalize_uvx_tool_args(arguments: dict[str, Any]) -> dict[str, Any]:
    """Merge ``help_path`` into ``args_list`` for subcommand help probes."""
    args = dict(arguments or {})
    help_path = args.get("help_path") or args.get("help_subcommand")
    if isinstance(help_path, str):
        help_path = [help_path]
    raw_list = args.get("args_list") or args.get("args") or []
    if isinstance(raw_list, str):
        raw_list = [raw_list]
    prefix = [str(x).strip() for x in list(help_path or []) if str(x).strip()]
    merged = prefix + [str(x) for x in list(raw_list)]
    if merged:
        args["args_list"] = merged
    return args


def _strip_exe(name: str) -> str:
    return name[:-4] if name.lower().endswith(".exe") else name


def _executable_guess_from_install_name(install_name: str) -> str:
    base = _strip_exe(install_name.strip())
    if base.endswith("-cli"):
        return base[: -len("-cli")]
    return base


def infer_with_packages_from_inputs(
    arguments: dict[str, Any],
    *,
    attachments: Sequence[dict[str, Any]] | None = None,
) -> list[str]:
    """Add format-plugin deps when the invoked CLI matches a registered family."""
    existing = list(arguments.get("with_packages") or arguments.get("with") or [])
    if isinstance(existing, str):
        existing = [existing]
    seen = {str(x).strip() for x in existing if str(x).strip()}

    package = str(arguments.get("package") or "").strip()
    from_spec = str(arguments.get("from_spec") or arguments.get("from") or "").strip() or None
    family_id = resolve_cli_plugin_family(package, from_spec)
    if family_id is None:
        return sorted(seen)

    extension_plugins = _CLI_PLUGIN_FAMILIES.get(family_id, {})
    extensions: set[str] = set()
    for raw in arguments.get("args_list") or []:
        suffix = Path(str(raw)).suffix.lower()
        if suffix:
            extensions.add(suffix)
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        for key in ("local_path", "filename", "storage_relative_path"):
            suffix = Path(str(att.get(key) or "")).suffix.lower()
            if suffix:
                extensions.add(suffix)
    for ext in extensions:
        for dep in extension_plugins.get(ext, ()):
            seen.add(dep)
    return sorted(seen)


def uvx_attempt_fingerprint(arguments: dict[str, Any]) -> tuple[Any, ...]:
    args = normalize_uvx_tool_args(arguments)
    raw_list = args.get("args_list") or []
    if isinstance(raw_list, str):
        raw_list = [raw_list]
    with_pkgs = args.get("with_packages") or args.get("with") or []
    if isinstance(with_pkgs, str):
        with_pkgs = [with_pkgs]
    return (
        str(args.get("package") or "").strip(),
        str(args.get("from_spec") or args.get("from") or "").strip() or None,
        tuple(str(x) for x in list(raw_list)),
        bool(args.get("help_only") or args.get("help")),
        tuple(sorted(str(x).strip() for x in list(with_pkgs) if str(x).strip())),
    )


_DELIVERY_STATE_SKIP_CODES = {
    "pending_delivery",
    "duplicate_attempt",
    "disallowed_invocation",
}


def is_help_invocation(arguments: dict[str, Any] | None) -> bool:
    """True when the call is a help probe rather than a delivering command."""
    args = normalize_uvx_tool_args(arguments or {})
    return bool(
        args.get("help_only")
        or args.get("help")
        or is_probe_attempt(args)
    )


def pending_delivery_cli(
    attempts: Sequence[dict[str, Any]] | None,
) -> dict[str, str | None] | None:
    """Return the CLI that has a successful help probe waiting for a delivering run.

    A new package or a second help probe is not allowed until a delivering
    invocation of this CLI has been attempted (or help-contract preflight
    rejected it). Failed probes do not create a pending delivery.
    """
    pending: dict[str, str | None] | None = None
    for attempt in attempts or []:
        if not isinstance(attempt, dict):
            continue
        if str(attempt.get("code") or "") in _DELIVERY_STATE_SKIP_CODES:
            continue
        if is_probe_attempt(attempt):
            if attempt.get("ok"):
                package = str(attempt.get("package") or "").strip()
                if package:
                    pending = {
                        "package": package,
                        "from_spec": str(attempt.get("from_spec") or "").strip() or None,
                    }
            continue
        pending = None
    return pending


def invocation_matches_pending(
    arguments: dict[str, Any] | None,
    pending: dict[str, str | None] | None,
) -> bool:
    if not pending:
        return True
    args = normalize_uvx_tool_args(arguments or {})
    return _same_cli_identity(
        str(pending.get("package") or ""),
        str(args.get("package") or ""),
    )


def has_successful_probe_for_cli(
    attempts: Sequence[dict[str, Any]] | None,
    *,
    package: str,
    from_spec: str | None = None,
) -> bool:
    del from_spec
    expected = str(package or "").strip()
    if not expected:
        return False
    for attempt in attempts or []:
        if not isinstance(attempt, dict) or not attempt.get("ok"):
            continue
        if not is_probe_attempt(attempt):
            continue
        if _same_cli_identity(expected, str(attempt.get("package") or "")):
            return True
    return False


def pending_delivery_block_error(
    arguments: dict[str, Any],
    pending: dict[str, str | None],
    *,
    fingerprint: tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    """Reject a second probe or a different CLI while a delivering run is due."""
    package = str(pending.get("package") or "").strip()
    from_spec = pending.get("from_spec")
    identity = f"package={package!r}"
    if from_spec:
        identity += f" from_spec={from_spec!r}"
    return {
        "ok": False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "package": (arguments or {}).get("package"),
        "from_spec": (arguments or {}).get("from_spec") or (arguments or {}).get("from"),
        "args_list": list((arguments or {}).get("args_list") or []),
        "error": (
            f"Help probe already succeeded for {identity}. "
            "Call run_uvx with help_only=false on that same CLI using only "
            "the allowed subcommands and flags. Do not probe another package "
            "until that delivering command has run."
        ),
        "code": "pending_delivery",
        "fingerprint": fingerprint,
        "pending_package": package,
        "pending_from_spec": from_spec,
        "help_only": bool((arguments or {}).get("help_only") or (arguments or {}).get("help")),
    }


def is_duplicate_failed_attempt(
    fingerprint: tuple[Any, ...],
    prior_attempts: Sequence[dict[str, Any]],
) -> bool:
    for attempt in prior_attempts:
        if attempt.get("ok"):
            continue
        prior_fp = attempt.get("fingerprint")
        if prior_fp == fingerprint:
            return True
        if prior_fp is None:
            reconstructed = uvx_attempt_fingerprint(
                {
                    "package": attempt.get("package"),
                    "from_spec": attempt.get("from_spec"),
                    "args_list": attempt.get("args_list") or [],
                    "help_only": attempt.get("help_only"),
                    "with_packages": attempt.get("with_packages") or [],
                }
            )
            if reconstructed == fingerprint:
                return True
    return False


def preflight_uvx_tool_args(
    arguments: dict[str, Any],
    *,
    prior_attempts: Sequence[dict[str, Any]] | None = None,
    attachments: Sequence[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Normalize and validate uvx args. Returns (args, error_result)."""
    args = normalize_uvx_tool_args(arguments)
    corrections: list[str] = []
    package = str(args.get("package") or "").strip()
    from_spec = str(args.get("from_spec") or args.get("from") or "").strip() or None

    if package.endswith("-cli") and not from_spec:
        from_spec = package
        package = _executable_guess_from_install_name(package)
        args["from_spec"] = from_spec
        args["package"] = package
        corrections.append(
            f"set from_spec={from_spec!r} and package={package!r} "
            "(install name differs from executable)"
        )

    if from_spec and package == from_spec:
        guessed = _executable_guess_from_install_name(from_spec)
        if guessed != package:
            args["package"] = guessed
            package = guessed
            corrections.append(f"set package={guessed!r} (executable name)")

    inferred = infer_with_packages_from_inputs(args, attachments=attachments)
    if inferred:
        args["with_packages"] = inferred

    fingerprint = uvx_attempt_fingerprint(args)
    pending = pending_delivery_cli(prior_attempts)
    if pending is not None:
        help_like = is_help_invocation(args)
        same_cli = invocation_matches_pending(args, pending)
        if help_like or not same_cli:
            blocked = pending_delivery_block_error(
                args, pending, fingerprint=fingerprint
            )
            blocked["preflight_corrected"] = bool(corrections)
            blocked["preflight_notes"] = corrections
            return args, blocked
    if prior_attempts and is_duplicate_failed_attempt(fingerprint, prior_attempts):
        return args, {
            "ok": False,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "package": args.get("package"),
            "args_list": list(args.get("args_list") or []),
            "error": (
                "Duplicate failed uvx invocation blocked. "
                "Change package/from_spec/args_list/with_packages before retrying."
            ),
            "code": "duplicate_attempt",
            "fingerprint": fingerprint,
            "preflight_corrected": bool(corrections),
            "preflight_notes": corrections,
        }

    contract_error = disallowed_invocation_error(
        args,
        collect_probe_contract(
            prior_attempts,
            package=str(args.get("package") or ""),
            from_spec=str(args.get("from_spec") or args.get("from") or "") or None,
        ),
        fingerprint=fingerprint,
        corrections=corrections,
    )
    if contract_error is not None:
        return args, contract_error

    if corrections:
        args["preflight_corrected"] = True
        args["preflight_notes"] = corrections
    return args, None


def remediate_uvx_tool_args(
    arguments: dict[str, Any],
    stderr: str,
) -> dict[str, Any] | None:
    """Return corrected args from uvx stderr, or None if no rule matches."""
    text = (stderr or "").strip()
    if not text:
        return None

    args = dict(arguments)
    changed = False

    use_match = _UVX_USE_INSTEAD_RE.search(text)
    if use_match:
        args["from_spec"] = use_match.group(1)
        args["package"] = _strip_exe(use_match.group(2))
        changed = True
    else:
        not_provided = _EXECUTABLE_NOT_PROVIDED_RE.search(text)
        available = _AVAILABLE_EXECUTABLE_RE.search(text)
        if not_provided:
            install_name = not_provided.group(2)
            if not args.get("from_spec"):
                args["from_spec"] = install_name
                changed = True
            if available:
                args["package"] = _strip_exe(available.group(1))
                changed = True
            elif install_name.endswith("-cli"):
                args["package"] = _executable_guess_from_install_name(install_name)
                changed = True

    if not changed:
        return None
    args["remediated"] = True
    return normalize_uvx_tool_args(args)


def parse_subcommands_from_help(stdout: str) -> list[str]:
    """Extract subcommand names from a typical Click help screen."""
    commands: list[str] = []
    in_commands = False
    for line in (stdout or "").splitlines():
        if re.match(r"^Commands:\s*$", line.strip(), re.I):
            in_commands = True
            continue
        if in_commands:
            if not line.strip():
                break
            match = _CLI_COMMAND_RE.match(line)
            if match:
                commands.append(match.group(1))
    return commands


def parse_flags_from_help(stdout: str) -> list[str]:
    """Extract short and long flags from a typical Options/Flags help section."""
    flags: list[str] = []
    in_options = False
    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if _OPTION_SECTION_RE.match(stripped):
            in_options = True
            continue
        if in_options and (_SECTION_STOP_RE.match(stripped) or not stripped):
            if stripped:
                break
            continue
        if not in_options:
            continue
        for token in _FLAG_TOKEN_RE.findall(line):
            if token not in flags:
                flags.append(token)
    return flags


def parse_probe_contract(stdout: str) -> dict[str, list[str]]:
    """Turn help text into an allowed subcommand/flag list."""
    return {
        "subcommands": parse_subcommands_from_help(stdout),
        "flags": parse_flags_from_help(stdout),
    }


def _looks_like_path(token: str) -> bool:
    text = str(token or "")
    if not text or text in {".", ".."}:
        return False
    if "/" in text or "\\" in text:
        return True
    return bool(Path(text).suffix)


def _looks_like_command_name(token: str) -> bool:
    text = str(token or "").strip()
    return bool(text) and bool(_COMMAND_NAME_RE.match(text)) and not _looks_like_path(text)


def _leading_command_path(
    raw_list: Sequence[str],
    help_path: Sequence[str] | None = None,
) -> tuple[str, ...]:
    if help_path:
        return tuple(
            str(x).strip()
            for x in help_path
            if str(x).strip() and str(x).strip() not in {"--help", "-h"}
        )
    path: list[str] = []
    for token in raw_list:
        text = str(token).strip()
        if not text or text in {"--help", "-h"}:
            continue
        if text.startswith("-"):
            break
        if not _looks_like_command_name(text):
            break
        path.append(text)
    return tuple(path)


def _extract_flag_tokens(tokens: Sequence[str]) -> list[str]:
    flags: list[str] = []
    index = 0
    items = [str(x) for x in tokens]
    while index < len(items):
        token = items[index]
        if token == "--":
            break
        if token.startswith("--"):
            name = token.split("=", 1)[0]
            flags.append(name)
            index += 1
            if "=" not in token and index < len(items) and not items[index].startswith("-"):
                index += 1
            continue
        if (
            token.startswith("-")
            and token != "-"
            and not re.match(r"^-\d", token)
        ):
            if len(token) == 2:
                flags.append(token)
                index += 1
                if index < len(items) and not items[index].startswith("-"):
                    index += 1
                continue
            for char in token[1:]:
                if char.isalpha():
                    flags.append(f"-{char}")
            index += 1
            continue
        index += 1
    return flags


def _split_invocation(
    raw_list: Sequence[str],
    known_subcommands: Sequence[str],
) -> tuple[tuple[str, ...], list[str]]:
    known = set(known_subcommands)
    tokens = [str(x) for x in raw_list]
    path: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"--help", "-h"}:
            index += 1
            continue
        if token.startswith("-"):
            break
        if token in known:
            path.append(token)
            index += 1
            continue
        break
    return tuple(path), _extract_flag_tokens(tokens[index:])


def _first_positional(raw_list: Sequence[str]) -> str | None:
    for token in raw_list:
        text = str(token).strip()
        if not text or text.startswith("-"):
            continue
        return text
    return None


def _did_you_mean(token: str, allowed: Sequence[str]) -> str | None:
    matches = difflib.get_close_matches(token, list(allowed), n=1, cutoff=0.5)
    return matches[0] if matches else None


def _same_cli_identity(expected: str, attempt_package: str) -> bool:
    left = expected.strip().lower()
    right = attempt_package.strip().lower()
    if not left or not right:
        return True
    if left == right:
        return True
    return _executable_guess_from_install_name(left) == _executable_guess_from_install_name(
        right
    )


def collect_probe_contract(
    prior_attempts: Sequence[dict[str, Any]] | None,
    *,
    package: str,
    from_spec: str | None = None,
) -> dict[str, Any]:
    """Merge allowed subcommands/flags from successful help probes for this tool."""
    del from_spec
    subcommands: list[str] = []
    flags_by_path: dict[tuple[str, ...], list[str]] = {}
    expected = str(package or "").strip().lower()
    for attempt in prior_attempts or []:
        if not attempt.get("ok"):
            continue
        if not (
            is_probe_attempt(attempt)
            or attempt.get("help_only")
            or attempt.get("help")
        ):
            continue
        attempt_package = str(attempt.get("package") or "").strip().lower()
        if not _same_cli_identity(expected, attempt_package):
            continue
        path = tuple(
            str(x)
            for x in (
                attempt.get("probe_path")
                or _leading_command_path(
                    list(attempt.get("args_list") or []),
                    attempt.get("help_path"),
                )
            )
        )
        parsed = parse_probe_contract(str(attempt.get("stdout") or ""))
        subs = list(attempt.get("allowed_subcommands") or parsed["subcommands"])
        flags = list(attempt.get("allowed_flags") or parsed["flags"])
        if subs and not path:
            for name in subs:
                if name not in subcommands:
                    subcommands.append(name)
        if flags:
            bucket = flags_by_path.setdefault(path, [])
            for flag in flags:
                if flag not in bucket:
                    bucket.append(flag)
    return {"subcommands": subcommands, "flags_by_path": flags_by_path}


def _flags_for_path(
    contract: dict[str, Any],
    path: tuple[str, ...],
) -> list[str] | None:
    flags_by_path = contract.get("flags_by_path") or {}
    if path in flags_by_path:
        merged: list[str] = []
        for flag in list(flags_by_path.get((), [])) + list(flags_by_path[path]):
            if flag not in merged:
                merged.append(flag)
        return merged
    if path:
        return None
    root = flags_by_path.get(())
    return list(root) if root else None


def format_probe_contract_lines(contract: dict[str, Any] | None) -> list[str]:
    if not contract:
        return []
    subcommands = list(contract.get("subcommands") or [])
    flags_by_path = contract.get("flags_by_path") or {}
    if not subcommands and not flags_by_path:
        return []
    lines = ["Allowed from help (use only these in the next delivering call):"]
    if subcommands:
        lines.append("subcommands: " + ", ".join(subcommands))
    for path, flags in flags_by_path.items():
        label = " ".join(path) if path else "(root)"
        if flags:
            lines.append(f"flags [{label}]: " + ", ".join(flags))
    return lines


def attach_probe_contract(result: dict[str, Any], invocation: dict[str, Any]) -> dict[str, Any]:
    """Record the allowed list on a successful help probe result."""
    payload = dict(result)
    probe_like = {
        **payload,
        "help_only": invocation.get("help_only") or invocation.get("help") or payload.get("help_only"),
        "args_list": invocation.get("args_list") or payload.get("args_list") or [],
    }
    if not payload.get("ok") or not is_probe_attempt(probe_like):
        return payload
    contract = parse_probe_contract(str(payload.get("stdout") or ""))
    path = _leading_command_path(
        list(invocation.get("args_list") or payload.get("args_list") or []),
        invocation.get("help_path") or payload.get("help_path"),
    )
    payload["allowed_subcommands"] = contract["subcommands"]
    payload["allowed_flags"] = contract["flags"]
    payload["probe_path"] = list(path)
    return payload


def disallowed_invocation_error(
    arguments: dict[str, Any],
    contract: dict[str, Any],
    *,
    fingerprint: tuple[Any, ...],
    corrections: Sequence[str] | None = None,
) -> dict[str, Any] | None:
    """Reject a delivering call that is not on the help-derived allowed list."""
    if arguments.get("help_only") or arguments.get("help") or is_probe_attempt(arguments):
        return None
    subcommands = list(contract.get("subcommands") or [])
    flags_by_path = contract.get("flags_by_path") or {}
    if not subcommands and not flags_by_path:
        return None

    raw_list = list(arguments.get("args_list") or [])
    path, flags = _split_invocation(raw_list, subcommands)
    first = _first_positional(raw_list)
    reason = ""
    allowed_flags = _flags_for_path(contract, path) or []

    if subcommands:
        if first and first not in subcommands and _looks_like_command_name(first):
            hint = _did_you_mean(first, subcommands)
            reason = f"Unknown subcommand {first!r}."
            if hint:
                reason += f" Did you mean {hint!r}?"
        elif first and first not in subcommands:
            reason = (
                f"Delivering call is missing an allowed subcommand. "
                f"Allowed subcommands: {', '.join(subcommands)}."
            )
        elif not first:
            reason = (
                "Delivering call is missing an allowed subcommand. "
                f"Allowed subcommands: {', '.join(subcommands)}."
            )

    if not reason:
        checked_flags = _flags_for_path(contract, path)
        if checked_flags is not None:
            allowed = set(checked_flags) | {"--help", "-h"}
            for flag in flags:
                if flag not in allowed:
                    hint = _did_you_mean(flag, sorted(allowed))
                    reason = f"Unknown flag {flag!r}."
                    if hint:
                        reason += f" Did you mean {hint!r}?"
                    allowed_flags = checked_flags
                    break

    if not reason:
        return None

    extra = ""
    if subcommands:
        extra += f" Allowed subcommands: {', '.join(subcommands)}."
    if allowed_flags:
        extra += f" Allowed flags: {', '.join(allowed_flags)}."
    return {
        "ok": False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "package": arguments.get("package"),
        "args_list": raw_list,
        "error": (reason + extra).strip(),
        "code": "disallowed_invocation",
        "fingerprint": fingerprint,
        "allowed_subcommands": subcommands,
        "allowed_flags": allowed_flags,
        "preflight_corrected": bool(corrections),
        "preflight_notes": list(corrections or []),
    }


def goal_subcommand_hints(instruction: str, success_criteria: str = "") -> list[str]:
    combined = f"{instruction} {success_criteria}".strip()
    hints: list[str] = []
    for pattern, name in _GOAL_SUBCOMMAND_HINTS:
        if pattern.search(combined) and name not in hints:
            hints.append(name)
    return hints


def help_ladder_followup_args(
    *,
    base_arguments: dict[str, Any],
    help_stdout: str,
    instruction: str,
    success_criteria: str,
    completed_subcommand_helps: Sequence[str],
) -> list[dict[str, Any]]:
    """Return subcommand help probes to run after a successful top-level help."""
    available = parse_subcommands_from_help(help_stdout)
    if not available:
        return []
    raw_args = list(base_arguments.get("args_list") or [])
    if raw_args and not (base_arguments.get("help_only") or base_arguments.get("help")):
        return []
    if raw_args and str(raw_args[-1]) in {"--help", "-h"}:
        raw_args = raw_args[:-1]
    if raw_args:
        return []

    wanted = [
        hint for hint in goal_subcommand_hints(instruction, success_criteria) if hint in available
    ]
    followups: list[dict[str, Any]] = []
    for subcommand in wanted:
        if subcommand in completed_subcommand_helps:
            continue
        probe = dict(base_arguments)
        probe["help_only"] = True
        probe["help_path"] = [subcommand]
        probe["args_list"] = []
        followups.append(probe)
    return followups


def classify_uvx_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return structured failure insight: error_class, retryable, suggested_next."""
    if result.get("ok"):
        if is_probe_attempt(result):
            return {
                "error_class": "probe",
                "retryable": True,
                "suggested_next": (
                "Help probe succeeded. Next run_uvx MUST be a delivering command "
                "(help_only=false) on this same CLI using only the allowed "
                "subcommands and flags; do not probe this or another package."
                ),
            }
        return {"error_class": "success", "retryable": False, "suggested_next": ""}

    code = str(result.get("code") or "").strip()
    stderr = str(result.get("stderr") or result.get("error") or "").strip()
    stderr_lower = stderr.lower()

    if code == "pending_delivery":
        return {
            "error_class": "blocked_pending_delivery",
            "retryable": True,
            "suggested_next": str(result.get("error") or "").strip()
            or (
                "Run the delivering command on the probed CLI "
                "(help_only=false); do not start another help probe."
            ),
        }

    if code == "duplicate_attempt":
        return {
            "error_class": "blocked_duplicate",
            "retryable": False,
            "suggested_next": (
                "Duplicate failed invocation blocked. Change package, from_spec, "
                "args_list, or with_packages before retrying."
            ),
        }

    if code == "disallowed_invocation":
        allowed_subs = result.get("allowed_subcommands") or []
        allowed_flags = result.get("allowed_flags") or []
        parts = ["Invocation is not on the help-derived allowed list."]
        if allowed_subs:
            parts.append("Allowed subcommands: " + ", ".join(str(x) for x in allowed_subs) + ".")
        if allowed_flags:
            parts.append("Allowed flags: " + ", ".join(str(x) for x in allowed_flags) + ".")
        parts.append("Change args_list to match help; do not invent flags or subcommands.")
        return {
            "error_class": "blocked_contract",
            "retryable": False,
            "suggested_next": " ".join(parts),
        }

    if _EXECUTABLE_NOT_PROVIDED_RE.search(stderr) or _UVX_USE_INSTEAD_RE.search(stderr):
        return {
            "error_class": "permanent",
            "retryable": False,
            "suggested_next": (
                "Install name differs from executable. Set from_spec to the install "
                "package and package to the console script (see stderr)."
            ),
        }

    if code in {"invalid_package", "invalid_args", "cli_disabled"}:
        return {
            "error_class": "permanent",
            "retryable": False,
            "suggested_next": "Fix tool arguments; this invocation cannot succeed as-is.",
        }

    if result.get("help_ladder"):
        return {
            "error_class": "probe",
            "retryable": not bool(result.get("ok")),
            "suggested_next": result.get("suggested_next")
            or "Automated subcommand help probe.",
        }

    if is_probe_attempt(result):
        return {
            "error_class": "probe",
            "retryable": True,
            "suggested_next": (
                "Help probe failed. Fix package/from_spec or try a different "
                "subcommand in help_path before retrying."
            ),
        }

    if "timed out" in stderr_lower or code == "uvx_missing":
        return {
            "error_class": "transient",
            "retryable": True,
            "suggested_next": "Transient failure; retry after correcting environment or args.",
        }

    if result.get("preflight_corrected") and result.get("preflight_notes"):
        notes = "; ".join(str(x) for x in result.get("preflight_notes") or [])
        return {
            "error_class": "permanent",
            "retryable": False,
            "suggested_next": notes or "Apply preflight correction before retrying.",
        }

    return {
        "error_class": "permanent",
        "retryable": False,
        "suggested_next": (
            "Read stderr, change strategy, and do not repeat the same invocation."
        ),
    }


def enrich_uvx_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    """Attach structured error insight fields to a uvx tool result payload."""
    payload = dict(result)
    insight = classify_uvx_tool_result(payload)
    payload.update(insight)
    return payload


def _attempt_invocation_label(attempt: dict[str, Any]) -> str:
    parts = [f"package={attempt.get('package')!r}"]
    from_spec = attempt.get("from_spec")
    if from_spec:
        parts.append(f"from_spec={from_spec!r}")
    args_list = attempt.get("args_list") or []
    if args_list:
        parts.append(f"args_list={list(args_list)!r}")
    if attempt.get("help_only") or attempt.get("help"):
        parts.append("help_only=true")
    if attempt.get("help_ladder"):
        parts.append("help_ladder=true")
    return " ".join(parts)


def summarize_uvx_attempt_line(attempt: dict[str, Any], index: int) -> str:
    """One-line ledger entry for a prior uvx attempt."""
    enriched = enrich_uvx_tool_result(attempt) if "error_class" not in attempt else attempt
    status = "OK" if enriched.get("ok") else "FAILED"
    error_class = enriched.get("error_class") or "unknown"
    line = (
        f"{index}. [{status}/{error_class}] run_uvx {_attempt_invocation_label(enriched)}"
    )
    suggested = str(enriched.get("suggested_next") or "").strip()
    if suggested:
        return f"{line} → {suggested}"
    if not enriched.get("ok"):
        err = str(enriched.get("error") or enriched.get("stderr") or "").strip()
        if err:
            short = err.replace("\n", " ")[:140]
            return f"{line} → {short}"
    return line


def build_uvx_attempt_ledger(
    attempts: Sequence[dict[str, Any]],
    *,
    max_attempts: int,
) -> str:
    """Compact attempt ledger for injection before each executor ReAct round."""
    if not attempts:
        return ""
    lines = [
        "Attempt ledger (do not repeat failed invocations):",
        *[summarize_uvx_attempt_line(att, i) for i, att in enumerate(attempts, 1)],
    ]
    used = len(attempts)
    remaining = max(0, max_attempts - used)
    lines.append(
        f"Budget: {used}/{max_attempts} tool attempts recorded; {remaining} remaining."
    )
    pending = pending_delivery_cli(attempts)
    if pending is not None:
        identity = f"package={pending.get('package')!r}"
        if pending.get("from_spec"):
            identity += f" from_spec={pending.get('from_spec')!r}"
        lines.append(
            f"Pending delivery: {identity}. Next run_uvx MUST be help_only=false "
            "on this CLI using only the allowed list. Do not probe another package."
        )
    else:
        lines.append(
            "When error_class is permanent, blocked_duplicate, or blocked_contract, "
            "change package/from_spec/args_list/with_packages — do not retry the same call."
        )
    pending_package = str((pending or {}).get("package") or "")
    lines.extend(
        format_probe_contract_lines(
            collect_probe_contract(attempts, package=pending_package)
        )
    )
    return "\n".join(lines)


def _result_from_uvx(
    result: Any,
    *,
    extra: dict[str, Any] | None = None,
    fingerprint: tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    payload = result.as_dict() if hasattr(result, "as_dict") else dict(result)
    if fingerprint is not None:
        payload["fingerprint"] = fingerprint
    if extra:
        payload.update(extra)
    return enrich_uvx_tool_result(payload)


def run_uvx_with_recovery(
    arguments: dict[str, Any],
    *,
    prior_attempts: Sequence[dict[str, Any]] | None = None,
    attachments: Sequence[dict[str, Any]] | None = None,
    instruction: str = "",
    success_criteria: str = "",
) -> dict[str, Any]:
    """Preflight, execute, remediate-retry, and optional help-ladder follow-ups."""
    args, preflight_error = preflight_uvx_tool_args(
        arguments,
        prior_attempts=prior_attempts,
        attachments=attachments,
    )
    fingerprint = uvx_attempt_fingerprint(args)
    if preflight_error is not None:
        return enrich_uvx_tool_result(preflight_error)

    def _invoke(inv: dict[str, Any]) -> dict[str, Any]:
        package = str(inv.get("package") or "").strip()
        raw_list = inv.get("args_list") or []
        if isinstance(raw_list, str):
            raw_list = [raw_list]
        cwd = inv.get("cwd") or inv.get("working_dir")
        help_only = bool(inv.get("help_only") or inv.get("help"))
        from_spec = inv.get("from_spec") or inv.get("from")
        with_packages = inv.get("with_packages") or inv.get("with") or []
        if isinstance(with_packages, str):
            with_packages = [with_packages]
        try:
            result = run_uvx(
                package,
                list(raw_list),
                cwd=cwd,
                help_only=help_only,
                from_spec=str(from_spec).strip() if from_spec else None,
                with_packages=list(with_packages),
            )
        except UvxRunnerError as exc:
            return enrich_uvx_tool_result(
                {
                    "ok": False,
                    "exit_code": None,
                    "stdout": "",
                    "stderr": str(exc),
                    "package": package,
                    "args_list": list(raw_list),
                    "error": str(exc),
                    "code": exc.code,
                    "fingerprint": uvx_attempt_fingerprint(inv),
                }
            )
        meta: dict[str, Any] = {}
        if inv.get("preflight_corrected"):
            meta["preflight_corrected"] = True
            meta["preflight_notes"] = inv.get("preflight_notes") or []
        if inv.get("remediated"):
            meta["remediated"] = True
        if inv.get("help_ladder"):
            meta["help_ladder"] = True
        return attach_probe_contract(
            _result_from_uvx(result, extra=meta, fingerprint=uvx_attempt_fingerprint(inv)),
            {**inv, "help_only": help_only, "args_list": list(raw_list)},
        )

    def _subcommand_help_ladder(
        help_result: dict[str, Any],
        base_args: dict[str, Any],
    ) -> list[dict[str, Any]]:
        extra: list[dict[str, Any]] = []
        completed = [
            str(x)
            for attempt in (prior_attempts or [])
            for x in (attempt.get("args_list") or [])[:1]
            if attempt.get("help_only") or attempt.get("help")
        ]
        for followup in help_ladder_followup_args(
            base_arguments=base_args,
            help_stdout=str(help_result.get("stdout") or ""),
            instruction=instruction,
            success_criteria=success_criteria,
            completed_subcommand_helps=completed,
        ):
            followup["help_ladder"] = True
            extra.append(_invoke(followup))
        return extra

    prefix_probes: list[dict[str, Any]] = []
    help_only = is_help_invocation(args)
    if not help_only and not has_successful_probe_for_cli(
        prior_attempts,
        package=str(args.get("package") or ""),
        from_spec=str(args.get("from_spec") or args.get("from") or "") or None,
    ):
        help_inv = {
            "package": args.get("package"),
            "from_spec": args.get("from_spec") or args.get("from"),
            "cwd": args.get("cwd") or args.get("working_dir"),
            "help_only": True,
            "args_list": [],
        }
        with_pkgs = args.get("with_packages") or args.get("with") or []
        if with_pkgs:
            help_inv["with_packages"] = with_pkgs
        help_result = _invoke(help_inv)
        prefix_probes.append(help_result)
        if help_result.get("ok"):
            prefix_probes.extend(_subcommand_help_ladder(help_result, help_inv))
        if not help_result.get("ok"):
            help_result["help_only"] = True
            if len(prefix_probes) > 1:
                help_result["ladder_attempts"] = prefix_probes[1:]
            return help_result
        contract_error = disallowed_invocation_error(
            args,
            collect_probe_contract(
                [*(prior_attempts or []), *prefix_probes],
                package=str(args.get("package") or ""),
                from_spec=str(args.get("from_spec") or args.get("from") or "") or None,
            ),
            fingerprint=fingerprint,
        )
        if contract_error is not None:
            contract_error["ladder_attempts"] = prefix_probes
            return enrich_uvx_tool_result(contract_error)

    primary = _invoke(args)
    ladder_attempts: list[dict[str, Any]] = []

    if not primary.get("ok"):
        remediated = remediate_uvx_tool_args(args, str(primary.get("stderr") or primary.get("error") or ""))
        if remediated is not None:
            retry_fp = uvx_attempt_fingerprint(remediated)
            if not (
                prior_attempts
                and is_duplicate_failed_attempt(retry_fp, [*prior_attempts, primary])
            ):
                primary = _invoke(remediated)

    raw_args = list(args.get("args_list") or [])
    is_top_level_help = help_only and (
        not raw_args or str(raw_args[-1]) in {"--help", "-h"}
    )
    if primary.get("ok") and is_top_level_help:
        ladder_attempts.extend(_subcommand_help_ladder(primary, args))

    combined_ladder = [*prefix_probes, *ladder_attempts]
    if combined_ladder:
        primary["ladder_attempts"] = combined_ladder
    return primary
