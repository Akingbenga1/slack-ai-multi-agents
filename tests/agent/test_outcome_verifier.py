"""Unit tests for independent outcome verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app.agent.outcome_verifier import (
    capture_working_scope,
    is_probe_attempt,
    verify_step_outcome,
)
from tests.agent.png_fixture import write_solid_png


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


def test_source_files_in_scope_do_not_satisfy_new_artifact_contract(tmp_path: Path) -> None:
    sources = [
        tmp_path / "a.png",
        tmp_path / "b.png",
        tmp_path / "c.png",
        tmp_path / "d.png",
    ]
    for src in sources:
        src.write_bytes(b"png-bytes")
    baseline = {path.resolve() for path in sources}
    result = verify_step_outcome(
        success_criteria=(
            "A new single PNG file is created that contains all four original "
            "images (a.png, b.png, c.png, d.png), and the original files remain unmodified."
        ),
        instruction="Combine the four PNG files into one image",
        result={
            "ok": True,
            "stdout": "displayed image in terminal",
            "attempts": [
                {
                    "ok": True,
                    "args_list": [str(sources[0])],
                    "stdout": "preview",
                }
            ],
        },
        scope_dir=tmp_path,
        known_inputs=sources,
        baseline_files=baseline,
    )
    assert result.verified is False
    assert result.method == "contract_unmet"


def test_new_artifact_verified_when_sources_already_in_scope(tmp_path: Path) -> None:
    sources = [tmp_path / "a.png", tmp_path / "b.png"]
    for src in sources:
        src.write_bytes(b"png-src")
    baseline = {path.resolve() for path in sources}
    combined = tmp_path / "combined.png"
    combined.write_bytes(b"png-combined")
    result = verify_step_outcome(
        success_criteria="A new PNG file is created combining a.png and b.png",
        instruction="Combine the PNG files",
        result={"ok": True, "output_file": str(combined)},
        scope_dir=tmp_path,
        known_inputs=sources,
        baseline_files=baseline,
    )
    assert result.verified is True
    assert result.method in {"artifact", "relations"}


@pytest.mark.parametrize(
    "criteria",
    [
        "A new report.pdf is produced with a footer on every page.",
        "A new report.pdf is produced with each page numbered.",
        "A new report.pdf is produced with all pages stamped.",
        "A new report.pdf is produced with a marker per page.",
    ],
)
def test_distribution_wording_does_not_require_several_files(
    tmp_path: Path, criteria: str
) -> None:
    """Wording about parts of one artifact must not demand extra artifacts."""
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-source")
    produced = tmp_path / "report_stamped.pdf"
    produced.write_bytes(b"%PDF-stamped")
    result = verify_step_outcome(
        success_criteria=criteria,
        instruction="Stamp the attached PDF and save a new file",
        result={
            "ok": True,
            "attempts": [{"ok": True, "args_list": ["stamp"], "stdout": "saved"}],
        },
        scope_dir=tmp_path,
        known_inputs=[source],
        baseline_files={source.resolve()},
    )
    assert result.verified is True
    assert result.method in {"artifact", "relations"}


def test_declared_artifact_count_is_binding(tmp_path: Path) -> None:
    produced = tmp_path / "section_1.pdf"
    produced.write_bytes(b"%PDF-1")
    result = verify_step_outcome(
        success_criteria="One PDF per section is created",
        instruction="Split the PDF into one file per section",
        result={"ok": True, "output_files": [str(produced)]},
        scope_dir=tmp_path,
        expected_artifact_count=3,
    )
    assert result.verified is False
    assert result.method == "contract_unmet"


def test_size_ceiling_marks_oversize_artifact_partial(tmp_path: Path) -> None:
    produced = tmp_path / "report.pdf"
    produced.write_bytes(b"x" * 140_507)
    result = verify_step_outcome(
        success_criteria="A new PDF is produced with file size below 100 kB",
        instruction="Make the file smaller than 100kB",
        result={"ok": True, "output_file": str(produced)},
        scope_dir=tmp_path,
    )
    assert result.verified is False
    assert result.method == "constraint_unmet"
    assert result.partial is True
    assert "140507" in result.reason


def test_size_ceiling_accepts_file_under_limit(tmp_path: Path) -> None:
    produced = tmp_path / "report.pdf"
    produced.write_bytes(b"x" * 80_000)
    result = verify_step_outcome(
        success_criteria="A new PDF is produced with file size below 100 kB",
        instruction="Compress the PDF",
        result={"ok": True, "output_file": str(produced)},
        scope_dir=tmp_path,
    )
    assert result.verified is True
    assert result.partial is False


def test_declared_artifact_count_read_from_structured_criteria(tmp_path: Path) -> None:
    first = tmp_path / "north.csv"
    second = tmp_path / "south.csv"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    result = verify_step_outcome(
        success_criteria={
            "text": "A CSV per region is created",
            "expected_artifact_count": 2,
        },
        instruction="Split the sheet by region",
        result={"ok": True, "output_files": [str(first), str(second)]},
        scope_dir=tmp_path,
    )
    assert result.verified is True
    assert result.method in {"artifact", "relations"}


def test_declared_output_that_is_an_input_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "a.png"
    source.write_bytes(b"png-src")
    result = verify_step_outcome(
        success_criteria="A new PNG file is created",
        instruction="Combine images",
        result={"ok": True, "output_file": str(source)},
        scope_dir=tmp_path,
        known_inputs=[source],
        baseline_files={source.resolve()},
    )
    assert result.verified is False


def test_transform_copy_of_input_fails_novel_vs_inputs(tmp_path: Path) -> None:
    source = write_solid_png(tmp_path / "a.png", rgb=(12, 34, 56))
    produced = write_solid_png(tmp_path / "a_out.png", rgb=(12, 34, 56))
    result = verify_step_outcome(
        success_criteria="Add a mark across the attached images and save new files",
        instruction="Add a mark across these images",
        result={"ok": True, "output_files": [str(produced)]},
        scope_dir=tmp_path,
        known_inputs=[source],
        baseline_files={source.resolve()},
    )
    assert result.verified is False
    assert result.method == "relation_unmet"
    assert result.partial is True


def test_transform_changed_content_passes_novel_vs_inputs(tmp_path: Path) -> None:
    source = write_solid_png(tmp_path / "a.png", rgb=(12, 34, 56))
    produced = write_solid_png(tmp_path / "a_out.png", rgb=(200, 10, 10))
    result = verify_step_outcome(
        success_criteria="Add a mark across the attached images and save new files",
        instruction="Add a mark across these images",
        result={"ok": True, "output_files": [str(produced)]},
        scope_dir=tmp_path,
        known_inputs=[source],
        baseline_files={source.resolve()},
    )
    assert result.verified is True
    assert result.method == "relations"


def test_structured_relations_are_binding(tmp_path: Path) -> None:
    source = write_solid_png(tmp_path / "in.png")
    produced = write_solid_png(tmp_path / "out.png", rgb=(1, 2, 3))
    result = verify_step_outcome(
        success_criteria={
            "text": "new marked images",
            "relations": [
                {"type": "produced"},
                {"type": "novel_vs_inputs"},
                {"type": "opens_as", "as": "image"},
                {"type": "count", "equals": 1},
            ],
        },
        instruction="Transform the attached images",
        result={"ok": True, "output_files": [str(produced)]},
        scope_dir=tmp_path,
        known_inputs=[source],
        baseline_files={source.resolve()},
    )
    assert result.verified is True
    assert result.method == "relations"


def test_unreadable_declared_tokens_are_uncertain(tmp_path: Path) -> None:
    source = write_solid_png(tmp_path / "in.png")
    produced = write_solid_png(tmp_path / "out.png", rgb=(9, 8, 7))
    result = verify_step_outcome(
        success_criteria={
            "relations": [
                {"type": "produced"},
                {"type": "contains_declared", "tokens": ["CONFIDENTIAL"]},
            ]
        },
        instruction="Mark the attached images",
        result={"ok": True, "output_files": [str(produced)]},
        scope_dir=tmp_path,
        known_inputs=[source],
        baseline_files={source.resolve()},
    )
    assert result.verified is False
    assert result.method == "uncertain"
