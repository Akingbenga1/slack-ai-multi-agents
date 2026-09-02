"""Independent outcome verification for executor steps.

Verifies observable results against ``success_criteria`` contracts without
assuming a single domain (files, records, API payloads, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ARTIFACT_SIGNALS = re.compile(
    r"\b("
    r"exists|created|written|saved|output|artifact|record|stored|"
    r"uploaded|generated|exported|rendered|merged|produced|file"
    r")\b",
    re.IGNORECASE,
)
_INFORMATIONAL_SIGNALS = re.compile(
    r"\b("
    r"summarize|summarise|explain|compare|describe|list|recap|"
    r"answer|report|bullet|stdout|output text"
    r")\b",
    re.IGNORECASE,
)
_PROBE_TOKENS = frozenset({"--help", "-h", "--version", "-V", "-?"})
_QUOTED_PATH = re.compile(r'[`"\']([^`"\']+)[`"\']')
_EXT_TOKEN = re.compile(r"\b[\w./\\-]+\.[A-Za-z0-9]{2,5}\b")
_SCOPE_HINT = re.compile(
    r"\b(?:under|in|into|to)\s+([\w./\\-]+/?[\w.-]*)",
    re.IGNORECASE,
)
_MULTI_ARTIFACT_SIGNALS = re.compile(
    r"\b("
    r"each|every|per\s+\w+|multiple|separate|one\s+file\s+per|"
    r"for\s+each|all\s+worksheets|all\s+sheets"
    r")\b",
    re.IGNORECASE,
)
_PRESERVE_ORIGINAL_SIGNALS = re.compile(
    r"\b(untouched|unchanged|without\s+modif|do\s+not\s+(?:modify|delete|overwrite)|"
    r"remains?\s+untouched|original\s+(?:file\s+)?(?:remains?|stays?))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    reason: str
    method: str


def criteria_text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        return str(raw.get("text") or raw.get("criteria") or "").strip()
    return str(raw).strip()


def is_probe_attempt(attempt: dict[str, Any]) -> bool:
    if attempt.get("help_only") or attempt.get("probe") or attempt.get("dry_run"):
        return True
    args = attempt.get("args_list") or []
    if any(str(token) in _PROBE_TOKENS for token in args):
        return True
    tool = str(attempt.get("tool") or "").strip()
    if tool == "run_uvx" and attempt.get("help_only"):
        return True
    return False


def delivering_attempts(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in attempts if a.get("ok") and not is_probe_attempt(a)]


def goal_kind(criteria: str, instruction: str) -> str:
    combined = f"{criteria} {instruction}".strip()
    if not combined:
        return "informational"
    if _ARTIFACT_SIGNALS.search(combined) and not _INFORMATIONAL_SIGNALS.search(
        criteria
    ):
        return "artifact"
    if _INFORMATIONAL_SIGNALS.search(combined):
        return "informational"
    if _ARTIFACT_SIGNALS.search(combined):
        return "artifact"
    return "informational"


def expects_multiple_artifacts(criteria: str, instruction: str = "") -> bool:
    combined = f"{criteria} {instruction}".strip()
    return bool(combined and _MULTI_ARTIFACT_SIGNALS.search(combined))


def expects_original_preserved(criteria: str, instruction: str = "") -> bool:
    combined = f"{criteria} {instruction}".strip()
    return bool(combined and _PRESERVE_ORIGINAL_SIGNALS.search(combined))


def _artifact_paths_from_payload(payload: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    raw_files = payload.get("output_files")
    if isinstance(raw_files, list):
        for item in raw_files:
            path = Path(str(item))
            key = str(path.resolve()) if path.exists() else str(path)
            if key not in seen:
                seen.add(key)
                paths.append(path)
    for key in ("output_file", "path", "output_path"):
        raw = payload.get(key)
        if not raw:
            continue
        path = Path(str(raw))
        key_text = str(path.resolve()) if path.exists() else str(path)
        if key_text not in seen:
            seen.add(key_text)
            paths.append(path)
    verified: list[Path] = []
    for path in paths:
        if path.is_file() and path.stat().st_size > 0:
            verified.append(path.resolve())
    return verified


def _output_dir_from_attempt(attempt: dict[str, Any], scope: Path | None) -> Path | None:
    from api.app.agent.uvx_runner import infer_output_dir_from_args

    args = attempt.get("args_list") or []
    cwd = attempt.get("cwd") or (str(scope) if scope else None)
    return infer_output_dir_from_args(args, cwd=cwd)


def _artifacts_in_scope(
    scope: Path,
    *,
    extensions: set[str] | None = None,
    min_count: int = 1,
) -> list[Path]:
    found: list[Path] = []
    for entry in scope.rglob("*"):
        if not entry.is_file() or entry.stat().st_size <= 0:
            continue
        if extensions and entry.suffix.lower() not in extensions:
            continue
        found.append(entry.resolve())
    if len(found) < min_count:
        return []
    return found


def path_hints_from_criteria(criteria: str) -> list[str]:
    hints: list[str] = []
    seen: set[str] = set()
    for match in _QUOTED_PATH.finditer(criteria):
        token = match.group(1).strip()
        if token and token not in seen:
            seen.add(token)
            hints.append(token)
    for match in _EXT_TOKEN.finditer(criteria):
        token = match.group(0).strip()
        if token and token not in seen:
            seen.add(token)
            hints.append(token)
    for match in _SCOPE_HINT.finditer(criteria):
        token = match.group(1).strip()
        if token and token not in seen:
            seen.add(token)
            hints.append(token)
    return hints


def _resolve_hint(hint: str, scope: Path | None) -> Path | None:
    text = hint.strip().replace("\\", "/")
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_file():
        return candidate.resolve()
    if scope and scope.is_dir():
        direct = (scope / text).resolve()
        if direct.is_file():
            return direct
        by_name = (scope / candidate.name).resolve()
        if by_name.is_file():
            return by_name
        for entry in scope.rglob(candidate.name):
            if entry.is_file():
                return entry.resolve()
    return None


def _artifact_path_from_payload(payload: dict[str, Any]) -> Path | None:
    paths = _artifact_paths_from_payload(payload)
    return paths[0] if paths else None


def _verify_artifact(
    criteria: str,
    result: dict[str, Any],
    *,
    scope: Path | None,
    instruction: str = "",
) -> VerificationResult:
    direct_paths = _artifact_paths_from_payload(result)
    if direct_paths:
        if expects_multiple_artifacts(criteria, instruction):
            if len(direct_paths) >= 2:
                return VerificationResult(
                    True,
                    f"verified {len(direct_paths)} artifacts",
                    "artifact",
                )
        else:
            return VerificationResult(
                True, f"artifact verified at {direct_paths[0]}", "artifact"
            )

    attempts = result.get("attempts")
    if isinstance(attempts, list):
        collected: list[Path] = []
        for attempt in reversed(delivering_attempts(attempts)):
            collected.extend(_artifact_paths_from_payload(attempt))
            if collected:
                break
        if collected:
            if expects_multiple_artifacts(criteria, instruction):
                if len(collected) >= 2:
                    return VerificationResult(
                        True,
                        f"verified {len(collected)} artifacts from attempts",
                        "artifact",
                    )
            else:
                return VerificationResult(
                    True,
                    f"artifact verified at {collected[0]}",
                    "artifact",
                )

        if expects_multiple_artifacts(criteria, instruction) and scope and scope.is_dir():
            extensions = {
                Path(h).suffix.lower()
                for h in path_hints_from_criteria(criteria)
                if Path(h).suffix
            } or {".xlsx", ".xls", ".csv"}
            for attempt in reversed(delivering_attempts(attempts)):
                out_dir = _output_dir_from_attempt(attempt, scope)
                search_root = out_dir if out_dir and out_dir.is_dir() else scope
                found = _artifacts_in_scope(
                    search_root,
                    extensions=extensions,
                    min_count=2,
                )
                if len(found) >= 2:
                    return VerificationResult(
                        True,
                        f"verified {len(found)} scoped artifacts under {search_root}",
                        "artifact",
                    )

    for hint in path_hints_from_criteria(criteria):
        resolved = _resolve_hint(hint, scope)
        if resolved is not None and resolved.stat().st_size > 0:
            return VerificationResult(
                True, f"contract hint matched {resolved}", "artifact"
            )

    if scope and scope.is_dir() and criteria:
        extensions = {
            Path(h).suffix.lower() for h in path_hints_from_criteria(criteria) if Path(h).suffix
        }
        if extensions:
            for entry in scope.rglob("*"):
                if entry.is_file() and entry.suffix.lower() in extensions:
                    if entry.stat().st_size > 0:
                        return VerificationResult(
                            True,
                            f"scoped artifact verified at {entry.resolve()}",
                            "artifact",
                        )

    return VerificationResult(
        False, "expected observable artifact not verified", "contract_unmet"
    )


def _verify_informational(result: dict[str, Any]) -> VerificationResult:
    attempts = result.get("attempts")
    if isinstance(attempts, list):
        if any(a.get("ok") for a in attempts) and not delivering_attempts(attempts):
            return VerificationResult(
                False, "only exploration attempts completed", "probe_rejected"
            )
        for attempt in reversed(delivering_attempts(attempts)):
            stdout = str(attempt.get("stdout") or "").strip()
            if len(stdout) >= 20:
                return VerificationResult(
                    True, "delivering tool output verified", "informational"
                )

    for key in ("done_text", "stdout"):
        text = str(result.get(key) or "").strip()
        if len(text) >= 40:
            return VerificationResult(
                True, "substantive response verified", "informational"
            )

    return VerificationResult(
        False, "insufficient verified content for goal", "contract_unmet"
    )


def verify_step_outcome(
    *,
    success_criteria: Any,
    instruction: str | None,
    result: dict[str, Any],
    scope_dir: str | Path | None = None,
) -> VerificationResult:
    """Verify ``result`` against the step contract."""
    criteria = criteria_text(success_criteria)
    instruction_text = (instruction or "").strip()
    scope = Path(scope_dir).resolve() if scope_dir else None
    attempts = result.get("attempts")
    if isinstance(attempts, list):
        if any(a.get("ok") for a in attempts) and not delivering_attempts(attempts):
            return VerificationResult(
                False, "only exploration attempts completed", "probe_rejected"
            )
    if is_probe_attempt(result):
        return VerificationResult(
            False, "exploration result is not delivery", "probe_rejected"
        )

    kind = goal_kind(criteria, instruction_text)

    artifact_check = _verify_artifact(
        criteria, result, scope=scope, instruction=instruction_text
    )
    if artifact_check.verified:
        return artifact_check

    if kind == "artifact" and criteria:
        return artifact_check

    if kind == "informational":
        info_check = _verify_informational(result)
        if info_check.verified:
            return info_check

    if result.get("ok") is True and not criteria:
        return VerificationResult(True, "no contract; process signal accepted", "process")

    if result.get("ok") is True and criteria:
        info_check = _verify_informational(result)
        if info_check.verified:
            return info_check

    if result.get("ok") is not True and artifact_check.verified:
        return artifact_check

    if result.get("ok") is True:
        return VerificationResult(
            False, "outcome could not be verified against contract", "contract_unmet"
        )

    return VerificationResult(
        False,
        str(result.get("error") or "step reported failure"),
        "contract_unmet",
    )


def capture_working_scope(scope_dir: str | Path | None, *, limit: int = 40) -> dict[str, Any]:
    """Compact snapshot of relevant external state under ``scope_dir``."""
    if not scope_dir:
        return {"scope": None, "entries": []}
    root = Path(scope_dir)
    if not root.is_dir():
        return {"scope": str(root), "entries": [], "missing": True}
    entries: list[dict[str, Any]] = []
    for entry in sorted(root.rglob("*")):
        if not entry.is_file():
            continue
        try:
            entries.append(
                {
                    "path": str(entry.relative_to(root)).replace("\\", "/"),
                    "bytes": entry.stat().st_size,
                }
            )
        except OSError:
            continue
        if len(entries) >= limit:
            break
    return {"scope": str(root.resolve()), "entries": entries, "truncated": len(entries) >= limit}


def combine_results_for_plan_check(step_results: dict[str, Any]) -> dict[str, Any]:
    """Merge prior step payloads for plan-level verification."""
    combined: dict[str, Any] = {"ok": False, "attempts": []}
    for value in step_results.values():
        if not isinstance(value, dict):
            continue
        if value.get("ok") is True:
            combined["ok"] = True
        for key in ("output_file", "path", "stdout", "done_text"):
            if value.get(key) and not combined.get(key):
                combined[key] = value.get(key)
        attempts = value.get("attempts")
        if isinstance(attempts, list):
            combined["attempts"].extend(attempts)
    if not combined["attempts"]:
        combined.pop("attempts", None)
    return combined
