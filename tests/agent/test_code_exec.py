"""Workspace action contracts: library policy, failure typing, real uvx runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.app.agent.code_exec import (
    classify_python_result,
    inspect_workspace,
    run_python,
    validate_libs,
)
from api.app.agent.uvx_runner import resolve_uvx_prefix
from api.app.agent.workspace import create_run_workspace
from api.app.settings import Settings

uvx_available = pytest.mark.skipif(
    resolve_uvx_prefix() is None, reason="uvx/uv not installed on PATH"
)


@pytest.fixture
def workspace(tmp_path: Path):
    return create_run_workspace(
        client_id="t", run_key="r", attachments=[], base_dir=tmp_path
    )


def test_validate_libs_accepts_names_and_extras():
    libs, error = validate_libs(["pillow", "markitdown[pdf]"], settings=Settings())
    assert error is None
    assert libs == ["pillow", "markitdown[pdf]"]


def test_validate_libs_rejects_injection_shapes():
    _, error = validate_libs(["pillow; rm -rf /"], settings=Settings())
    assert error and "invalid library name" in error


def test_validate_libs_enforces_count_ceiling():
    _, error = validate_libs(
        [f"pkg{i}" for i in range(5)], settings=Settings(agent_python_max_libs=3)
    )
    assert error and "too many libraries" in error


def test_validate_libs_enforces_allowlist_when_configured():
    settings = Settings(agent_python_libs_allowlist="pillow pypdf")
    allowed, error = validate_libs(["pillow"], settings=settings)
    assert error is None and allowed == ["pillow"]

    _, denied = validate_libs(["requests"], settings=settings)
    assert denied and "not permitted by policy" in denied


def test_missing_module_is_typed_as_recoverable():
    insight = classify_python_result(
        ok=False,
        stdout="",
        stderr="ModuleNotFoundError: No module named 'fitz'",
        produced=[],
    )
    assert insight["error_class"] == "missing_library"
    assert insight["retryable"] is True
    assert "fitz" in insight["suggested_next"]


def test_script_exception_is_typed_distinctly():
    insight = classify_python_result(
        ok=False,
        stdout="",
        stderr="Traceback...\nValueError: bad input",
        produced=[],
    )
    assert insight["error_class"] == "python_error"
    assert "ValueError" in insight["suggested_next"]


def test_success_without_output_is_flagged_for_artifact_goals():
    insight = classify_python_result(ok=True, stdout="hi", stderr="", produced=[])
    assert insight["error_class"] == "success_no_output"
    assert insight["retryable"] is True


def test_run_python_requires_a_script(workspace):
    result = run_python({}, workspace=workspace, settings=Settings())
    assert result["ok"] is False
    assert result["error_class"] == "invalid_action"


def test_inspect_workspace_is_not_delivery(workspace):
    (workspace.root / "notes.txt").write_text("hello there", encoding="utf-8")
    result = inspect_workspace(
        {"paths": ["notes.txt"]}, workspace=workspace, settings=Settings()
    )
    assert result["ok"] is True
    # Inspection must never satisfy an outcome contract.
    assert result["probe"] is True
    assert result["peeks"][0]["head"] == "hello there"


def test_inspect_workspace_reports_unknown_paths(workspace):
    result = inspect_workspace(
        {"paths": ["../outside.txt"]}, workspace=workspace, settings=Settings()
    )
    assert result["peeks"][0]["error"] == "not found in workspace"


@uvx_available
def test_run_python_executes_and_attributes_artifacts(workspace):
    """Standard-library script through real uvx, with output detection."""
    script = (
        "from pathlib import Path\n"
        "Path('summary.txt').write_text('two lines\\nof text', encoding='utf-8')\n"
        "print('wrote summary.txt')\n"
    )
    result = run_python(
        {"script": script, "purpose": "write summary"},
        workspace=workspace,
        settings=Settings(),
    )
    assert result["ok"] is True, result
    assert result["error_class"] == "success"
    assert result["produced_relative"] == ["summary.txt"]
    assert "wrote summary.txt" in result["stdout"]
    assert (workspace.root / "summary.txt").exists()
    # The script itself is internal and never reported as an artifact.
    assert all("scripts" not in p for p in result["produced_relative"])


@uvx_available
def test_run_python_surfaces_missing_library_from_real_run(workspace):
    result = run_python(
        {"script": "import definitely_not_a_real_module_xyz\n"},
        workspace=workspace,
        settings=Settings(),
    )
    assert result["ok"] is False
    assert result["error_class"] == "missing_library"


@uvx_available
def test_run_python_injects_requested_library(workspace):
    """`uvx --with <lib>` makes any PyPI distribution available to the script."""
    result = run_python(
        {
            "script": "import PIL; print('pillow', PIL.__version__)",
            "libs": ["pillow"],
        },
        workspace=workspace,
        settings=Settings(),
    )
    assert result["ok"] is True, result
    assert "pillow" in result["stdout"]
