"""Unit tests for uvx runner command assembly and output detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from api.app.agent.uvx_runner import (
    UvxRunnerError,
    _build_uvx_cmd,
    _validate_with_packages,
    infer_output_dir_from_args,
    resolve_output_files,
    run_uvx,
)


def test_build_uvx_cmd_with_from_and_with() -> None:
    cmd = _build_uvx_cmd(
        ["uvx"],
        package="pyexcel",
        args=["split", "book.xlsx", "out_"],
        from_spec="pyexcel-cli",
        with_packages=["pyexcel-xlsx"],
    )
    assert cmd == [
        "uvx",
        "--from",
        "pyexcel-cli",
        "--with",
        "pyexcel-xlsx",
        "pyexcel",
        "split",
        "book.xlsx",
        "out_",
    ]


def test_validate_with_packages_rejects_unsafe_names() -> None:
    assert _validate_with_packages(["pyexcel-xlsx"]) == ["pyexcel-xlsx"]
    with pytest.raises(UvxRunnerError):
        _validate_with_packages(["bad;package"])


def test_infer_output_dir_from_args(tmp_path: Path) -> None:
    out = tmp_path / "split_out"
    args = ["split", "a.xlsx", "p_", "--output-dir", "split_out"]
    resolved = infer_output_dir_from_args(args, cwd=tmp_path)
    assert resolved == out.resolve()


def test_resolve_output_files_detects_multiple_in_output_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "split_out"
    out_dir.mkdir()
    before = {}
    (out_dir / "a.xlsx").write_bytes(b"x")
    (out_dir / "b.xlsx").write_bytes(b"y")
    files = resolve_output_files(
        args_list=["split", "src.xlsx", "p_", "--output-dir", "split_out"],
        cwd=tmp_path,
        ok=True,
        help_only=False,
        before_snapshot=before,
        output_dir_snapshot=before,
        scan_root=out_dir,
    )
    assert len(files) == 2


@patch("api.app.agent.uvx_runner.subprocess.run")
@patch("api.app.agent.uvx_runner.resolve_uvx_prefix", return_value=["uvx"])
@patch("api.app.agent.uvx_runner.get_settings")
def test_run_uvx_passes_with_packages(
    mock_settings: MagicMock,
    _mock_prefix: MagicMock,
    mock_run: MagicMock,
) -> None:
    settings = MagicMock()
    settings.cli_tools_enabled = True
    settings.cli_tools_timeout_seconds = 30.0
    settings.cli_tools_max_output_bytes = 10000
    mock_settings.return_value = settings
    mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

    result = run_uvx(
        "pyexcel",
        ["--help"],
        help_only=True,
        from_spec="pyexcel-cli",
        with_packages=["pyexcel-xlsx"],
    )

    assert result.ok is True
    assert result.with_packages == ("pyexcel-xlsx",)
    assert result.cmd == [
        "uvx",
        "--from",
        "pyexcel-cli",
        "--with",
        "pyexcel-xlsx",
        "pyexcel",
        "--help",
    ]
