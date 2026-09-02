"""Preflight, remediation, and help-ladder orchestration for ``run_uvx`` invocations."""

from __future__ import annotations

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
                    "Help probe succeeded. Run the delivering command next; "
                    "do not repeat the same help probe."
                ),
            }
        return {"error_class": "success", "retryable": False, "suggested_next": ""}

    code = str(result.get("code") or "").strip()
    stderr = str(result.get("stderr") or result.get("error") or "").strip()
    stderr_lower = stderr.lower()

    if code == "duplicate_attempt":
        return {
            "error_class": "blocked_duplicate",
            "retryable": False,
            "suggested_next": (
                "Duplicate failed invocation blocked. Change package, from_spec, "
                "args_list, or with_packages before retrying."
            ),
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
    lines.append(
        "When error_class is permanent or blocked_duplicate, change package/from_spec/"
        "args_list/with_packages — do not retry the same call."
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
        return _result_from_uvx(result, extra=meta, fingerprint=uvx_attempt_fingerprint(inv))

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

    help_only = bool(args.get("help_only") or args.get("help"))
    raw_args = list(args.get("args_list") or [])
    is_top_level_help = help_only and (
        not raw_args or str(raw_args[-1]) in {"--help", "-h"}
    )
    if primary.get("ok") and is_top_level_help:
        completed = [
            str(x)
            for attempt in (prior_attempts or [])
            for x in (attempt.get("args_list") or [])[:1]
            if attempt.get("help_only") or attempt.get("help")
        ]
        for followup in help_ladder_followup_args(
            base_arguments=args,
            help_stdout=str(primary.get("stdout") or ""),
            instruction=instruction,
            success_criteria=success_criteria,
            completed_subcommand_helps=completed,
        ):
            followup["help_ladder"] = True
            ladder_attempts.append(_invoke(followup))

    if ladder_attempts:
        primary["ladder_attempts"] = ladder_attempts
    return primary
