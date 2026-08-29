"""General multi-step handoff: output capture and prior-result formatting."""

from __future__ import annotations

from pathlib import Path

from api.app.agent.executor import _format_prior_step_results, _summarize_step_result
from api.app.agent.uvx_runner import (
    infer_output_path_from_args,
    resolve_output_file,
)


def test_infer_output_path_from_common_flags() -> None:
    assert infer_output_path_from_args(["a.pdf", "b.pdf", "-o", "merged.pdf"]) == "merged.pdf"
    assert infer_output_path_from_args(["--output", "out.csv"]) == "out.csv"
    assert infer_output_path_from_args(["--output=out.json"]) == "out.json"


def test_resolve_output_file_from_declared_flag(tmp_path: Path) -> None:
    target = tmp_path / "result.txt"
    target.write_text("done", encoding="utf-8")
    resolved = resolve_output_file(
        args_list=["input.txt", "-o", "result.txt"],
        cwd=tmp_path,
        ok=True,
        help_only=False,
    )
    assert resolved == str(target.resolve())


def test_resolve_output_file_from_single_new_file(tmp_path: Path) -> None:
    (tmp_path / "left.pdf").write_bytes(b"%PDF-1")
    before = {p.name: p.stat().st_mtime for p in tmp_path.iterdir() if p.is_file()}
    created = tmp_path / "output.pdf"
    created.write_bytes(b"%PDF-2")
    resolved = resolve_output_file(
        args_list=["left.pdf"],
        cwd=tmp_path,
        ok=True,
        help_only=False,
        before_snapshot=before,
    )
    assert resolved == str(created.resolve())


def test_prior_results_include_output_file_without_stdout() -> None:
    prior = {
        "step_0": {
            "ok": True,
            "stdout": "",
            "output_file": "/tmp/work/merged.pdf",
        }
    }
    block = _format_prior_step_results(prior)
    assert "output_file: /tmp/work/merged.pdf" in block
    assert block != "(none)"


def test_summarize_step_result_reads_nested_attempt_output() -> None:
    summary = _summarize_step_result(
        {
            "ok": True,
            "stdout": "",
            "attempts": [
                {"ok": True, "stdout": "", "output_file": "/data/out.csv"},
            ],
        }
    )
    assert "output_file: /data/out.csv" in summary
