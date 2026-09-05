"""Independent outcome verification for executor steps.

Verifies observable results against ``success_criteria`` contracts without
assuming a single domain (files, records, API payloads, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from api.app.agent.outcome_relations import (
    declared_count,
    evaluate_relations,
    has_contract,
    infer_relations,
    max_size_bytes,
    summarize_reports,
)
from api.app.agent.outcome_relations import (
    criteria_text as relation_criteria_text,
)

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
    partial: bool = False
    paths: tuple[str, ...] = ()


def max_size_bytes_from_contract(text: str) -> int | None:
    """Largest allowed artifact size when the contract states a ceiling."""
    return max_size_bytes(text)


def _apply_size_contract(
    paths: Sequence[Path],
    *,
    criteria: str,
    instruction: str,
    verified: VerificationResult,
) -> VerificationResult:
    if not verified.verified:
        return verified
    limit = max_size_bytes_from_contract(f"{criteria} {instruction}")
    if limit is None:
        return verified
    for path in paths:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > limit:
            return VerificationResult(
                False,
                f"{path.name} is {size} bytes; contract requires under {limit} bytes",
                "constraint_unmet",
                partial=True,
            )
    return verified


def criteria_text(raw: Any) -> str:
    return relation_criteria_text(raw)


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
    """Whether wording *suggests* several outputs.

    Advisory only. The same words describe distribution inside one artifact
    ("a footer on every page") and a set of artifacts ("one file per sheet"),
    so this widens where verification looks and never raises the bar.
    """
    combined = f"{criteria} {instruction}".strip()
    return bool(combined and _MULTI_ARTIFACT_SIGNALS.search(combined))


def declared_artifact_count(raw: Any) -> int | None:
    """Output cardinality when a contract states it explicitly."""
    return declared_count(raw)


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


def existing_files_in_scope(scope_dir: str | Path | None) -> set[Path]:
    """All files under a working scope at one moment (verification baseline)."""
    if not scope_dir:
        return set()
    root = Path(scope_dir)
    if not root.is_dir():
        return set()
    found: set[Path] = set()
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue
        try:
            found.add(entry.resolve())
        except OSError:
            continue
    return found


def _normalize_file_set(raw: Sequence[str | Path] | None) -> set[Path]:
    out: set[Path] = set()
    for item in raw or []:
        path = Path(str(item))
        try:
            if path.is_file():
                out.add(path.resolve())
        except OSError:
            continue
    return out


def _excluded_artifact_paths(
    *,
    known_inputs: Sequence[str | Path] | None,
    baseline_files: Sequence[str | Path] | set[Path] | None,
) -> set[Path]:
    """Inputs and pre-step files cannot satisfy a produced-artifact contract."""
    excluded = _normalize_file_set(known_inputs)
    if isinstance(baseline_files, set):
        for path in baseline_files:
            try:
                if path.is_file():
                    excluded.add(path.resolve())
            except OSError:
                continue
    else:
        excluded |= _normalize_file_set(baseline_files)
    return excluded


def _novel_artifacts(paths: Sequence[Path], excluded: set[Path]) -> list[Path]:
    novel: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in excluded or resolved in seen:
            continue
        if not resolved.is_file() or resolved.stat().st_size <= 0:
            continue
        seen.add(resolved)
        novel.append(resolved)
    return novel


def _artifacts_in_scope(
    scope: Path,
    *,
    extensions: set[str] | None = None,
    min_count: int = 1,
    exclude: set[Path] | None = None,
) -> list[Path]:
    found: list[Path] = []
    blocked = exclude or set()
    for entry in scope.rglob("*"):
        if not entry.is_file() or entry.stat().st_size <= 0:
            continue
        if extensions and entry.suffix.lower() not in extensions:
            continue
        resolved = entry.resolve()
        if resolved in blocked:
            continue
        found.append(resolved)
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


def _artifact_found(
    paths: Sequence[Path],
    *,
    source: str = "",
    criteria: str = "",
    instruction: str = "",
) -> VerificationResult:
    stored = tuple(str(path) for path in paths)
    if len(paths) == 1:
        found = VerificationResult(
            True, f"artifact verified at {paths[0]}", "artifact", paths=stored
        )
    else:
        suffix = f" from {source}" if source else ""
        found = VerificationResult(
            True,
            f"verified {len(paths)} artifacts{suffix}",
            "artifact",
            paths=stored,
        )
    return _with_paths(
        _apply_size_contract(
            paths, criteria=criteria, instruction=instruction, verified=found
        ),
        paths,
    )


def _with_paths(result: VerificationResult, paths: Sequence[Path]) -> VerificationResult:
    stored = tuple(str(path) for path in paths)
    if result.paths:
        return result
    return VerificationResult(
        result.verified,
        result.reason,
        result.method,
        partial=result.partial,
        paths=stored,
    )


def _verify_artifact(
    criteria: str,
    result: dict[str, Any],
    *,
    scope: Path | None,
    instruction: str = "",
    excluded: set[Path] | None = None,
    required_count: int | None = None,
) -> VerificationResult:
    blocked = excluded or set()
    # Only a declared count raises the bar. Cardinality guessed from wording is
    # a search hint, so a contract is never failed for producing one artifact
    # when nothing declared that several were due.
    required = max(1, int(required_count or 1))
    widen_search = expects_multiple_artifacts(criteria, instruction)

    direct_paths = _novel_artifacts(_artifact_paths_from_payload(result), blocked)
    if len(direct_paths) >= required:
        return _artifact_found(
            direct_paths, criteria=criteria, instruction=instruction
        )

    attempts = result.get("attempts")
    if isinstance(attempts, list):
        collected: list[Path] = []
        for attempt in reversed(delivering_attempts(attempts)):
            collected.extend(
                _novel_artifacts(_artifact_paths_from_payload(attempt), blocked)
            )
            if collected:
                break
        if len(collected) >= required:
            return _artifact_found(
                collected,
                source="attempts",
                criteria=criteria,
                instruction=instruction,
            )

        if widen_search and scope and scope.is_dir():
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
                    min_count=required,
                    exclude=blocked,
                )
                if len(found) >= required:
                    return _with_paths(
                        _apply_size_contract(
                            found,
                            criteria=criteria,
                            instruction=instruction,
                            verified=VerificationResult(
                                True,
                                f"verified {len(found)} scoped artifacts under {search_root}",
                                "artifact",
                            ),
                        ),
                        found,
                    )

    for hint in path_hints_from_criteria(criteria):
        resolved = _resolve_hint(hint, scope)
        if resolved is None or resolved.stat().st_size <= 0:
            continue
        if resolved in blocked:
            continue
        return _with_paths(
            _apply_size_contract(
                [resolved],
                criteria=criteria,
                instruction=instruction,
                verified=VerificationResult(
                    True, f"contract hint matched {resolved}", "artifact"
                ),
            ),
            [resolved],
        )

    if scope and scope.is_dir() and criteria:
        extensions = {
            Path(h).suffix.lower() for h in path_hints_from_criteria(criteria) if Path(h).suffix
        }
        if extensions:
            found = _artifacts_in_scope(
                scope,
                extensions=extensions,
                min_count=required,
                exclude=blocked,
            )
            if len(found) >= required:
                if len(found) == 1:
                    scoped = VerificationResult(
                        True,
                        f"scoped artifact verified at {found[0]}",
                        "artifact",
                    )
                else:
                    scoped = VerificationResult(
                        True,
                        f"verified {len(found)} scoped artifacts under {scope}",
                        "artifact",
                    )
                return _with_paths(
                    _apply_size_contract(
                        found,
                        criteria=criteria,
                        instruction=instruction,
                        verified=scoped,
                    ),
                    found,
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
    known_inputs: Sequence[str | Path] | None = None,
    baseline_files: Sequence[str | Path] | set[Path] | None = None,
    expected_artifact_count: int | None = None,
) -> VerificationResult:
    """Verify ``result`` against the step contract."""
    criteria = criteria_text(success_criteria)
    instruction_text = (instruction or "").strip()
    scope = Path(scope_dir).resolve() if scope_dir else None
    required_count = expected_artifact_count or declared_artifact_count(
        success_criteria
    )
    excluded = _excluded_artifact_paths(
        known_inputs=known_inputs,
        baseline_files=baseline_files,
    )
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
        criteria,
        result,
        scope=scope,
        instruction=instruction_text,
        excluded=excluded,
        required_count=required_count,
    )
    input_paths = [Path(p) for p in (known_inputs or [])]
    relations = infer_relations(
        success_criteria,
        instruction=instruction_text,
        has_inputs=any(path.is_file() for path in input_paths),
    )
    if artifact_check.verified and relations:
        produced = [Path(p) for p in artifact_check.paths if Path(p).is_file()]
        if not produced:
            produced = _novel_artifacts(
                _artifact_paths_from_payload(result), excluded
            )
        reports = evaluate_relations(
            relations,
            produced=produced,
            known_inputs=input_paths,
        )
        method, reason, partial = summarize_reports(reports)
        if method != "relations":
            return VerificationResult(
                False,
                reason,
                method,
                partial=partial,
                paths=tuple(str(p) for p in produced),
            )
        return VerificationResult(
            True,
            reason,
            method,
            paths=tuple(str(p) for p in produced),
        )
    if artifact_check.verified:
        return artifact_check

    if kind == "artifact" and (criteria or has_contract(success_criteria)):
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
