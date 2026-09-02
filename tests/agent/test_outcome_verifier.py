"""Unit tests for independent outcome verification."""

from __future__ import annotations

from pathlib import Path

from api.app.agent.outcome_verifier import (
    capture_working_scope,
    is_probe_attempt,
    verify_step_outcome,
)


def test_probe_attempt_rejected_even_when_ok() -> None:
    result = verify_step_outcome(
        success_criteria="CSV file exists",
        instruction="Convert spreadsheet",
        result={
            "ok": True,
            "stdout": "Usage: in2csv ...",
            "attempts": [
                {
                    "ok": True,
                    "help_only": True,
                    "args_list": ["--help"],
                    "stdout": "Usage: in2csv ...",
                }
            ],
        },
        scope_dir=None,
    )
    assert result.verified is False
    assert result.method == "probe_rejected"


def test_artifact_verified_from_result_path(tmp_path: Path) -> None:
    target = tmp_path / "merged.pdf"
    target.write_bytes(b"%PDF-1.4")
    result = verify_step_outcome(
        success_criteria="Combined PDF exists in output folder",
        instruction="Merge PDFs",
        result={"ok": False, "error": "executor stopped without success", "output_file": str(target)},
        scope_dir=tmp_path,
    )
    assert result.verified is True
    assert result.method == "artifact"


def test_artifact_verified_from_scope_hint_when_result_failed(tmp_path: Path) -> None:
    checker = tmp_path / "checker"
    checker.mkdir()
    target = checker / "Combined.pdf"
    target.write_bytes(b"%PDF-merged")
    result = verify_step_outcome(
        success_criteria='PDF exists under "checker/Combined.pdf"',
        instruction="Move merged PDF to checker",
        result={"ok": False, "error": "executor stopped without success", "attempts": []},
        scope_dir=tmp_path,
    )
    assert result.verified is True


def test_informational_goal_accepts_substantive_done_text() -> None:
    result = verify_step_outcome(
        success_criteria="Summarize the report in bullet points for email",
        instruction="Summarize report",
        result={
            "ok": True,
            "done_text": "- Revenue up 12%\n- Costs flat\n- Guidance unchanged for Q4 outlook.",
        },
        scope_dir=None,
    )
    assert result.verified is True
    assert result.method == "informational"


def test_no_contract_falls_back_to_process_signal() -> None:
    result = verify_step_outcome(
        success_criteria=None,
        instruction="Fetch channel history",
        result={"ok": True, "stdout": "ok"},
        scope_dir=None,
    )
    assert result.verified is True
    assert result.method == "process"


def test_capture_working_scope_lists_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
    snapshot = capture_working_scope(tmp_path)
    assert snapshot["scope"] == str(tmp_path.resolve())
    assert snapshot["entries"]


def test_is_probe_attempt_detects_help_flags() -> None:
    assert is_probe_attempt({"ok": True, "args_list": ["--help"]}) is True
    assert is_probe_attempt({"ok": True, "args_list": ["run"]}) is False


def test_multi_artifact_verified_from_output_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "split_out"
    out_dir.mkdir()
    first = out_dir / "sheet_a.xlsx"
    second = out_dir / "sheet_b.xlsx"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    result = verify_step_outcome(
        success_criteria="A new .xlsx file is created for each worksheet",
        instruction="Split workbook into separate files per sheet",
        result={
            "ok": True,
            "output_files": [str(first), str(second)],
            "attempts": [
                {
                    "ok": True,
                    "args_list": [
                        "split",
                        "book.xlsx",
                        "out_",
                        "--output-dir",
                        "split_out",
                    ],
                    "output_files": [str(first), str(second)],
                }
            ],
        },
        scope_dir=tmp_path,
    )
    assert result.verified is True
    assert result.method == "artifact"


def test_multi_artifact_verified_from_output_dir_in_scope(tmp_path: Path) -> None:
    out_dir = tmp_path / "split_out"
    out_dir.mkdir()
    (out_dir / "sheet_a.xlsx").write_bytes(b"a")
    (out_dir / "sheet_b.xlsx").write_bytes(b"b")
    result = verify_step_outcome(
        success_criteria="Each worksheet becomes its own separate .xlsx file",
        instruction="Split workbook per sheet",
        result={
            "ok": False,
            "error": "executor stopped without success",
            "attempts": [
                {
                    "ok": True,
                    "args_list": [
                        "split",
                        "book.xlsx",
                        "out_",
                        "--output-dir",
                        "split_out",
                    ],
                }
            ],
        },
        scope_dir=tmp_path,
    )
    assert result.verified is True
