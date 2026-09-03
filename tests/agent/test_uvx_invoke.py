"""Tests for uvx preflight, remediation, and help ladder."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.app.agent.uvx_invoke import (
    build_uvx_attempt_ledger,
    classify_uvx_tool_result,
    collect_probe_contract,
    enrich_uvx_tool_result,
    goal_subcommand_hints,
    help_ladder_followup_args,
    is_duplicate_failed_attempt,
    parse_flags_from_help,
    parse_subcommands_from_help,
    pending_delivery_cli,
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


_CLICK_ROOT_HELP = (
    "Usage: tool [OPTIONS] COMMAND [ARGS]...\n\n"
    "Options:\n"
    "  --help  Show this message and exit.\n\n"
    "Commands:\n"
    "  diff       diff two files\n"
    "  merge      Merge files into one\n"
    "  split      Split a file into parts\n"
)

_CLICK_SPLIT_HELP = (
    "Usage: tool split [OPTIONS] PATH\n\n"
    "Options:\n"
    "  -o, --output PATH  Write output here.\n"
    "  --help             Show this message and exit.\n"
)


def test_parse_flags_from_help() -> None:
    assert parse_flags_from_help(_CLICK_SPLIT_HELP) == ["-o", "--output", "--help"]
    assert parse_subcommands_from_help(_CLICK_ROOT_HELP) == ["diff", "merge", "split"]


def test_preflight_blocks_unknown_subcommand_after_help() -> None:
    prior = [
        {
            "ok": True,
            "help_only": True,
            "package": "tool",
            "args_list": ["--help"],
            "stdout": _CLICK_ROOT_HELP,
        }
    ]
    _, err = preflight_uvx_tool_args(
        {"package": "tool", "args_list": ["export", "input.csv"]},
        prior_attempts=prior,
    )
    assert err is not None
    assert err["code"] == "disallowed_invocation"
    assert "Unknown subcommand" in err["error"]
    assert "split" in err["allowed_subcommands"]


def test_preflight_blocks_unknown_flag_after_subcommand_help() -> None:
    prior = [
        {
            "ok": True,
            "help_only": True,
            "package": "tool",
            "args_list": ["--help"],
            "stdout": _CLICK_ROOT_HELP,
        },
        {
            "ok": True,
            "help_only": True,
            "package": "tool",
            "args_list": ["split", "--help"],
            "stdout": _CLICK_SPLIT_HELP,
            "probe_path": ["split"],
        },
    ]
    _, err = preflight_uvx_tool_args(
        {"package": "tool", "args_list": ["split", "input.csv", "--sheet", "1"]},
        prior_attempts=prior,
    )
    assert err is not None
    assert err["code"] == "disallowed_invocation"
    assert "--sheet" in err["error"]
    assert "--output" in err["allowed_flags"]


def test_preflight_allows_known_subcommand_and_flag() -> None:
    prior = [
        {
            "ok": True,
            "help_only": True,
            "package": "tool",
            "args_list": ["--help"],
            "stdout": _CLICK_ROOT_HELP,
        },
        {
            "ok": True,
            "help_only": True,
            "package": "tool",
            "args_list": ["split", "--help"],
            "stdout": _CLICK_SPLIT_HELP,
            "probe_path": ["split"],
        },
    ]
    args, err = preflight_uvx_tool_args(
        {"package": "tool", "args_list": ["split", "input.csv", "--output", "out.csv"]},
        prior_attempts=prior,
    )
    assert err is None
    assert args["args_list"][0] == "split"


def test_preflight_skips_help_contract_without_prior_help() -> None:
    _, err = preflight_uvx_tool_args(
        {"package": "tool", "args_list": ["split", "--sheet", "1"]},
    )
    assert err is None


def test_collect_probe_contract_merges_help() -> None:
    contract = collect_probe_contract(
        [
            {
                "ok": True,
                "help_only": True,
                "package": "tool",
                "args_list": ["--help"],
                "stdout": _CLICK_ROOT_HELP,
            },
            {
                "ok": True,
                "help_only": True,
                "package": "tool",
                "args_list": ["split", "--help"],
                "stdout": _CLICK_SPLIT_HELP,
            },
        ],
        package="tool",
    )
    assert "split" in contract["subcommands"]
    assert "--output" in contract["flags_by_path"][("split",)]


@patch("api.app.agent.uvx_invoke.run_uvx")
def test_run_uvx_with_recovery_does_not_execute_unknown_flag(
    mock_run_uvx: MagicMock,
) -> None:
    result = run_uvx_with_recovery(
        {"package": "tool", "args_list": ["export", "in.csv"]},
        prior_attempts=[
            {
                "ok": True,
                "help_only": True,
                "package": "tool",
                "args_list": ["--help"],
                "stdout": _CLICK_ROOT_HELP,
            }
        ],
    )
    assert result["ok"] is False
    assert result["code"] == "disallowed_invocation"
    mock_run_uvx.assert_not_called()


def test_classify_disallowed_invocation() -> None:
    insight = classify_uvx_tool_result(
        {
            "ok": False,
            "code": "disallowed_invocation",
            "allowed_subcommands": ["split"],
            "allowed_flags": ["--output"],
        }
    )
    assert insight["error_class"] == "blocked_contract"
    assert insight["retryable"] is False
    assert "split" in insight["suggested_next"]


def test_build_attempt_ledger_includes_allowed_list() -> None:
    ledger = build_uvx_attempt_ledger(
        [
            enrich_uvx_tool_result(
                {
                    "ok": True,
                    "package": "tool",
                    "args_list": ["--help"],
                    "help_only": True,
                    "stdout": _CLICK_ROOT_HELP,
                    "allowed_subcommands": ["diff", "merge", "split"],
                    "allowed_flags": ["--help"],
                }
            )
        ],
        max_attempts=4,
    )
    assert "Allowed from help" in ledger
    assert "split" in ledger


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
        max_attempts=4,
    )
    assert "Attempt ledger" in ledger
    assert "FAILED/permanent" in ledger
    assert "OK/probe" in ledger
    assert "Budget: 2/4" in ledger
    assert "Pending delivery" in ledger


def _successful_probe(package: str = "tool") -> dict:
    return enrich_uvx_tool_result(
        {
            "ok": True,
            "package": package,
            "args_list": ["--help"],
            "help_only": True,
            "stdout": "Usage: tool\n",
        }
    )


def test_pending_delivery_after_successful_probe() -> None:
    pending = pending_delivery_cli([_successful_probe("tool")])
    assert pending is not None
    assert pending["package"] == "tool"


def test_pending_delivery_cleared_after_delivering_attempt() -> None:
    pending = pending_delivery_cli(
        [
            _successful_probe("tool"),
            {"ok": False, "package": "tool", "args_list": ["run", "in.png"], "stdout": ""},
        ]
    )
    assert pending is None


def test_preflight_blocks_second_help_probe_while_pending() -> None:
    prior = [_successful_probe("tool")]
    _, err = preflight_uvx_tool_args(
        {"package": "tool", "help_only": True},
        prior_attempts=prior,
    )
    assert err is not None
    assert err["code"] == "pending_delivery"


def test_preflight_blocks_other_package_while_pending() -> None:
    prior = [_successful_probe("tool")]
    _, err = preflight_uvx_tool_args(
        {"package": "other", "help_only": True},
        prior_attempts=prior,
    )
    assert err is not None
    assert err["code"] == "pending_delivery"


def test_preflight_allows_delivering_command_on_probed_cli() -> None:
    prior = [_successful_probe("tool")]
    args, err = preflight_uvx_tool_args(
        {"package": "tool", "args_list": ["in.png", "out.png"]},
        prior_attempts=prior,
    )
    assert err is None
    assert args["package"] == "tool"


def test_failed_probe_does_not_pin_cli() -> None:
    prior = [
        {
            "ok": False,
            "package": "missing",
            "help_only": True,
            "args_list": ["--help"],
            "stderr": "not found",
        }
    ]
    assert pending_delivery_cli(prior) is None
    _, err = preflight_uvx_tool_args(
        {"package": "other", "help_only": True},
        prior_attempts=prior,
    )
    assert err is None


def test_classify_pending_delivery() -> None:
    insight = classify_uvx_tool_result(
        {
            "ok": False,
            "code": "pending_delivery",
            "error": "Help probe already succeeded for package='tool'.",
        }
    )
    assert insight["error_class"] == "blocked_pending_delivery"
    assert insight["retryable"] is True


@patch("api.app.agent.uvx_invoke.run_uvx")
def test_run_uvx_probes_help_before_first_delivering(mock_run_uvx: MagicMock) -> None:
    help_ok = MagicMock(
        ok=True,
        exit_code=0,
        stdout="Usage: tool\n",
        stderr="",
        package="tool",
        args_list=["--help"],
        cmd=[],
        error=None,
        output_file=None,
        output_files=(),
        with_packages=(),
    )
    help_ok.as_dict = lambda: {
        "ok": True,
        "exit_code": 0,
        "stdout": "Usage: tool\n",
        "stderr": "",
        "package": "tool",
        "args_list": ["--help"],
        "cmd": [],
        "help_only": True,
    }
    deliver_ok = MagicMock(
        ok=True,
        exit_code=0,
        stdout="wrote out.png",
        stderr="",
        package="tool",
        args_list=["in.png", "out.png"],
        cmd=[],
        error=None,
        output_file="out.png",
        output_files=("out.png",),
        with_packages=(),
    )
    deliver_ok.as_dict = lambda: {
        "ok": True,
        "exit_code": 0,
        "stdout": "wrote out.png",
        "stderr": "",
        "package": "tool",
        "args_list": ["in.png", "out.png"],
        "cmd": [],
        "output_file": "out.png",
        "output_files": ["out.png"],
    }
    mock_run_uvx.side_effect = [help_ok, deliver_ok]

    result = run_uvx_with_recovery(
        {"package": "tool", "args_list": ["in.png", "out.png"]},
    )
    assert result["ok"] is True
    assert mock_run_uvx.call_count == 2
    assert mock_run_uvx.call_args_list[0].kwargs["help_only"] is True
    assert mock_run_uvx.call_args_list[1].kwargs["help_only"] is False
    assert len(result.get("ladder_attempts") or []) == 1

