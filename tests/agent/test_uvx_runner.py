"""Unit tests for CLI output-directory inference used by outcome verification."""

from __future__ import annotations

from pathlib import Path

from api.app.agent.uvx_runner import infer_output_dir_from_args


def test_infer_output_dir_from_args(tmp_path: Path) -> None:
    out = tmp_path / "split_out"
    args = ["split", "a.xlsx", "p_", "--output-dir", "split_out"]
    resolved = infer_output_dir_from_args(args, cwd=tmp_path)
    assert resolved == out.resolve()


def test_infer_output_dir_from_equals_flag(tmp_path: Path) -> None:
    out = tmp_path / "dest"
    args = ["convert", "in.pdf", f"--outdir={out.name}"]
    resolved = infer_output_dir_from_args(args, cwd=tmp_path)
    assert resolved == out.resolve()


def test_infer_output_dir_missing_returns_none() -> None:
    assert infer_output_dir_from_args(["split", "a.xlsx"]) is None
