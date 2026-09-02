"""Tests for uvx preflight, remediation, and help ladder."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.app.agent.uvx_invoke import (
    build_uvx_attempt_ledger,
    classify_uvx_tool_result,
    enrich_uvx_tool_result,
    goal_subcommand_hints,
    help_ladder_followup_args,
    is_duplicate_failed_attempt,
    parse_subcommands_from_help,
    preflight_uvx_tool_args,
    remediate_uvx_tool_args,
    run_uvx_with_recovery,
    uvx_attempt_fingerprint,
)


def test_preflight_fixes_cli_install_name_as_executable() -> None:
    args, err = preflight_uvx_tool_args({"package": "pyexcel-cli"})
    assert err is None
    assert args["from_spec"] == "pyexcel-cli"
    assert args["package"] == "pyexcel"
    assert args.get("preflight_corrected") is True


def test_preflight_adds_xlsx_plugin_from_attachment() -> None:
    args, err = preflight_uvx_tool_args(
        {"package": "pyexcel", "from_spec": "pyexcel-cli", "args_list": ["split", "a.xlsx"]},
        attachments=[{"filename": "book.xlsx", "local_path": "/tmp/book.xlsx"}],
    )
    assert err is None
    assert "pyexcel-xlsx" in args["with_packages"]


def test_preflight_skips_format_plugins_for_unrelated_cli() -> None:
    args, err = preflight_uvx_tool_args(
        {"package": "ffmpeg", "args_list": ["-i", "clip.mp4", "out.wav"]},
        attachments=[{"filename": "book.xlsx", "local_path": "/tmp/book.xlsx"}],
    )
    assert err is None
    assert "pyexcel-xlsx" not in args.get("with_packages", [])
    assert not args.get("with_packages")


def test_remediate_from_uvx_stderr_use_instead() -> None:
    stderr = (
        "An executable named `pyexcel-cli` is not provided by package `pyexcel-cli`.\n"
        "Use `uvx --from pyexcel-cli pyexcel.exe` instead."
    )
    fixed = remediate_uvx_tool_args({"package": "pyexcel-cli"}, stderr)
    assert fixed is not None
    assert fixed["from_spec"] == "pyexcel-cli"
    assert fixed["package"] == "pyexcel"


def test_duplicate_failed_attempt_blocked() -> None:
    args = {
        "package": "pyexcel",
        "from_spec": "pyexcel-cli",
        "args_list": ["--help"],
        "help_only": True,
    }
    fp = uvx_attempt_fingerprint(args)
    _, err = preflight_uvx_tool_args(
        args,
        prior_attempts=[{"ok": False, "fingerprint": fp}],
    )
    assert err is not None
    assert err["code"] == "duplicate_attempt"


def test_is_duplicate_failed_attempt_matches_reconstructed_fingerprint() -> None:
    fp = uvx_attempt_fingerprint(
        {"package": "pyexcel", "from_spec": "pyexcel-cli", "args_list": ["--help"], "help_only": True}
    )
    assert is_duplicate_failed_attempt(
        fp,
        [
            {
                "ok": False,
                "package": "pyexcel",
                "from_spec": "pyexcel-cli",
                "args_list": ["--help"],
                "help_only": True,
            }
        ],
    )


def test_parse_subcommands_from_help() -> None:
    stdout = (
        "Usage: pyexcel [OPTIONS] COMMAND [ARGS]...\n\n"
        "Commands:\n"
        "  diff       diff two excel files\n"
        "  merge      Merge excel files into one\n"
        "  split      Split a multi-sheet file into single ones\n"
    )
    assert parse_subcommands_from_help(stdout) == ["diff", "merge", "split"]


def test_goal_subcommand_hints_split() -> None:
    assert "split" in goal_subcommand_hints(
        "Split the workbook into per-sheet files",
        "One file per worksheet is created",
    )


def test_help_ladder_followup_after_top_level_help() -> None:
    stdout = (
        "Commands:\n"
        "  split      Split a multi-sheet file into single ones\n"
        "  view       View an excel file\n"
    )
    followups = help_ladder_followup_args(
        base_arguments={"package": "pyexcel", "from_spec": "pyexcel-cli", "help_only": True},
        help_stdout=stdout,
        instruction="Split workbook per worksheet",
        success_criteria="One file per sheet",
        completed_subcommand_helps=[],
    )
    assert len(followups) == 1
    assert followups[0]["help_path"] == ["split"]


@patch("api.app.agent.uvx_invoke.run_uvx")
def test_run_uvx_with_recovery_preflight_before_invoke(mock_run_uvx: MagicMock) -> None:
    ok = MagicMock(
        ok=True,
        exit_code=0,
        stdout="Usage: pyexcel ...",
        stderr="",
        package="pyexcel",
        args_list=["--help"],
        cmd=[],
        error=None,
        output_file=None,
        output_files=(),
        with_packages=(),
    )
    ok.as_dict = lambda: {
        "ok": True,
        "exit_code": 0,
        "stdout": ok.stdout,
        "stderr": "",
        "package": "pyexcel",
        "args_list": ["--help"],
        "cmd": [],
    }
    mock_run_uvx.return_value = ok

    result = run_uvx_with_recovery(
        {"package": "pyexcel-cli", "help_only": True},
        instruction="split workbook",
    )
    assert result["ok"] is True
    assert result.get("preflight_corrected") is True
    mock_run_uvx.assert_called_once()
    assert mock_run_uvx.call_args.kwargs["from_spec"] == "pyexcel-cli"
    assert mock_run_uvx.call_args.args[0] == "pyexcel"


def test_classify_executable_not_provided_as_permanent() -> None:
    insight = classify_uvx_tool_result(
        {
            "ok": False,
            "stderr": (
                "An executable named `pyexcel-cli` is not provided by package "
                "`pyexcel-cli`.\nUse `uvx --from pyexcel-cli pyexcel.exe` instead."
            ),
            "package": "pyexcel-cli",
            "args_list": ["--help"],
            "help_only": True,
        }
    )
    assert insight["error_class"] == "permanent"
    assert insight["retryable"] is False
    assert "from_spec" in insight["suggested_next"]


def test_classify_probe_success() -> None:
    insight = classify_uvx_tool_result(
        {"ok": True, "package": "pyexcel", "args_list": ["--help"], "help_only": True}
    )
    assert insight["error_class"] == "probe"
    assert insight["retryable"] is True


def test_build_attempt_ledger_lists_failures() -> None:
    ledger = build_uvx_attempt_ledger(
        [
            enrich_uvx_tool_result(
                {
                    "ok": False,
                    "package": "pyexcel-cli",
                    "args_list": ["--help"],
                    "help_only": True,
                    "stderr": (
                        "An executable named `pyexcel-cli` is not provided by "
                        "package `pyexcel-cli`."
                    ),
                }
            ),
            enrich_uvx_tool_result(
                {
                    "ok": True,
                    "package": "pyexcel",
                    "from_spec": "pyexcel-cli",
                    "args_list": ["--help"],
                    "help_only": True,
                }
            ),
        ],
        max_attempts=8,
    )
    assert "Attempt ledger" in ledger
    assert "FAILED/permanent" in ledger
    assert "OK/probe" in ledger
    assert "Budget: 2/8" in ledger
    assert "do not repeat" in ledger.lower()
