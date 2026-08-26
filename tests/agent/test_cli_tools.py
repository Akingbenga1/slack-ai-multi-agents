"""CLI tool path resolution (cross-platform subprocess cwd/args)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.app.agent.tools import (
    ToolRef,
    _invoke_cli,
    _normalize_cli_path,
    _resolve_cli_args,
    _resolve_cli_working_dir,
)


def _msys_path(path: Path) -> str:
    """Build a Git-Bash-style /c/Users/... path from a native path."""
    resolved = path.resolve()
    drive = resolved.drive[:1].lower()
    tail = str(resolved)[3:].replace("\\", "/")
    return f"/{drive}/{tail}"


def test_normalize_cli_path_msys_to_native_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("api.app.agent.tools.os.name", "nt", raising=False)
    native = _normalize_cli_path(_msys_path(tmp_path))
    assert native == tmp_path.resolve()


def test_resolve_cli_working_dir_falls_back_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    settings = MagicMock()
    settings.upload_dir_path = tmp_path / "data" / "uploads"
    path = _resolve_cli_working_dir({"working_dir": "/nonexistent/path"}, settings)
    assert path == tmp_path.resolve()


def test_resolve_cli_args_finds_file_in_working_dir(tmp_path: Path):
    sample = tmp_path / "sample_users.xlsx"
    sample.write_bytes(b"xlsx")
    working = tmp_path
    resolved = _resolve_cli_args(
        ["sample_users.xlsx"],
        working_dir=working,
        search_dirs=[working],
    )
    assert resolved == [str(sample.resolve())]


def test_resolve_cli_args_preserves_flags(tmp_path: Path):
    resolved = _resolve_cli_args(
        ["-c", "Name,Email", "out.csv"],
        working_dir=tmp_path,
        search_dirs=[tmp_path],
    )
    assert resolved[0] == "-c"
    assert resolved[1] == "Name,Email"
    assert Path(resolved[2]).name == "out.csv"


def test_invoke_cli_uses_native_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sample = tmp_path / "sample_users.xlsx"
    sample.write_bytes(b"data")
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        return MagicMock(returncode=0, stdout="Name,Email\nAlice,a@x.com\n", stderr="")

    monkeypatch.setattr("api.app.agent.tools.subprocess.run", fake_run)
    monkeypatch.setattr(
        "api.app.settings.get_settings",
        lambda: MagicMock(
            cli_tools_enabled=True,
            cli_tools_timeout_seconds=30,
            cli_tools_max_output_bytes=1000,
            upload_dir_path=tmp_path / "uploads",
        ),
    )

    ref = ToolRef(
        name="csvkit",
        source="registry",
        kind="cli",
        config={
            "command": "in2csv",
            "working_dir": _msys_path(tmp_path),
        },
    )
    result = _invoke_cli(
        ref,
        {
            "subcommand": "in2csv",
            "args_list": ["sample_users.xlsx"],
            "output_file": "sample_users.csv",
        },
    )
    assert result["ok"] is True
    assert captured["cwd"] == str(tmp_path.resolve())
    assert captured["cmd"] == ["in2csv", str(sample.resolve())]
