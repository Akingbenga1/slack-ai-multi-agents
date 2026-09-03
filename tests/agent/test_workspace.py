"""Run workspace invariants: isolation, input safety, artifact attribution."""

from __future__ import annotations

from pathlib import Path

from api.app.agent.workspace import (
    RunWorkspace,
    create_run_workspace,
    promote_outputs,
    safe_component,
)


def _attachment(path: Path, name: str | None = None) -> dict[str, str]:
    return {"filename": name or path.name, "local_path": str(path)}


def test_inputs_are_staged_as_copies(tmp_path: Path):
    source_dir = tmp_path / "uploads"
    source_dir.mkdir()
    original = source_dir / "report.pdf"
    original.write_bytes(b"%PDF-original")

    workspace = create_run_workspace(
        client_id="tenant-1",
        run_key="run-1",
        attachments=[_attachment(original)],
        base_dir=tmp_path / "workspaces",
    )

    assert len(workspace.inputs) == 1
    staged = workspace.root / workspace.inputs[0].relative_path
    assert staged.read_bytes() == b"%PDF-original"
    assert staged.resolve() != original.resolve()

    # Mutating the staged copy must not reach the user's file.
    staged.write_bytes(b"%PDF-modified")
    assert original.read_bytes() == b"%PDF-original"


def test_workspace_is_isolated_from_unrelated_files(tmp_path: Path):
    """Artifacts are attributable because the baseline holds only our inputs."""
    source_dir = tmp_path / "uploads"
    source_dir.mkdir()
    wanted = source_dir / "a.png"
    wanted.write_bytes(b"png")
    (source_dir / "unrelated.xlsx").write_bytes(b"xlsx")
    (source_dir / "someone_elses.zip").write_bytes(b"zip")

    workspace = create_run_workspace(
        client_id="tenant-1",
        run_key="run-2",
        attachments=[_attachment(wanted)],
        base_dir=tmp_path / "workspaces",
    )
    listed = {entry["path"] for entry in workspace.listing()}
    assert listed == {"a.png"}


def test_files_since_reports_only_new_non_internal_files(tmp_path: Path):
    workspace = create_run_workspace(
        client_id="t", run_key="r", attachments=[], base_dir=tmp_path
    )
    baseline = workspace.snapshot()

    (workspace.root / "result.csv").write_text("a,b\n", encoding="utf-8")
    workspace.next_script_path("action").write_text("print(1)", encoding="utf-8")

    produced = workspace.files_since(baseline)
    assert [p.name for p in produced] == ["result.csv"]


def test_resolve_within_rejects_escapes(tmp_path: Path):
    workspace = create_run_workspace(
        client_id="t", run_key="r", attachments=[], base_dir=tmp_path
    )
    assert workspace.resolve_within("out/file.txt") is not None
    assert workspace.resolve_within("../escape.txt") is None
    assert workspace.resolve_within("~/secrets") is None
    assert workspace.resolve_within("") is None


def test_promote_outputs_copies_produced_not_inputs(tmp_path: Path):
    source_dir = tmp_path / "uploads"
    source_dir.mkdir()
    original = source_dir / "in.txt"
    original.write_text("input", encoding="utf-8")

    workspace = create_run_workspace(
        client_id="t",
        run_key="r",
        attachments=[_attachment(original)],
        base_dir=tmp_path / "ws",
    )
    (workspace.root / "out.txt").write_text("produced", encoding="utf-8")

    destination = tmp_path / "delivered"
    promoted = promote_outputs(workspace, destination=destination)

    assert [Path(p).name for p in promoted] == ["out.txt"]
    assert (destination / "out.txt").read_text(encoding="utf-8") == "produced"
    assert not (destination / "in.txt").exists()


def test_colliding_input_names_stay_addressable(tmp_path: Path):
    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()
    (first_dir / "data.csv").write_text("1", encoding="utf-8")
    (second_dir / "data.csv").write_text("2", encoding="utf-8")

    workspace = create_run_workspace(
        client_id="t",
        run_key="r",
        attachments=[
            _attachment(first_dir / "data.csv"),
            _attachment(second_dir / "data.csv"),
        ],
        base_dir=tmp_path / "ws",
    )
    relatives = [i.relative_path for i in workspace.inputs]
    assert relatives == ["data.csv", "data_2.csv"]
    assert (workspace.root / "data.csv").read_text(encoding="utf-8") == "1"
    assert (workspace.root / "data_2.csv").read_text(encoding="utf-8") == "2"


def test_safe_component_strips_paths_and_flag_prefixes():
    assert safe_component("../../etc/passwd") == "passwd"
    assert safe_component("--rf") == "rf"
    assert safe_component("a b;c.txt") == "a_b_c.txt"
    assert safe_component("") == "input"


def test_adopted_directory_reports_relative_paths(tmp_path: Path):
    workspace = RunWorkspace(root=tmp_path.resolve(), inputs=())
    target = tmp_path / "nested" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    assert workspace.relative_of(target) == "nested/file.txt"


def test_script_path_stays_within_platform_path_budget(tmp_path: Path):
    """A long model-written label must not push the script path past the limit."""
    workspace = create_run_workspace(
        client_id="11111111-1111-1111-1111-111111111111",
        run_key="fcfb8792-a5a0-426b-aa3e-e366428f6a71",
        base_dir=tmp_path / "data" / "workspaces",
    )
    label = (
        "Remove embedded font file streams so viewers substitute standard "
        "fonts Arial Times New Roman Brush Script are all common"
    )

    target = workspace.next_script_path(label)

    assert len(str(target.resolve())) <= 250
    assert target.name.startswith("01_")
    assert target.suffix == ".py"
    target.write_text("print(1)", encoding="utf-8")
    assert target.is_file()


def test_short_script_labels_are_left_intact(tmp_path: Path):
    workspace = create_run_workspace(
        client_id="tenant-1",
        run_key="run-1",
        base_dir=tmp_path / "workspaces",
    )
    target = workspace.next_script_path("Inspect the PDF")
    assert target.name == "01_Inspect_the_PDF.py"
