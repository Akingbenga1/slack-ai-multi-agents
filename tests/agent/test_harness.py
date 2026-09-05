"""Unit tests for Deep Agents harness helpers (no live LLM)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from api.app.agent.harness import (
    _build_user_message,
    _final_assistant_text,
    _message_text,
    run_deep_agent,
)
from api.app.agent.workspace import RunWorkspace, WorkspaceInput
from api.app.membership import DEMO_TENANT_ID


def test_message_text_handles_blocks() -> None:
    assert _message_text("hi") == "hi"
    assert _message_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "a\nb"


def test_final_assistant_text_from_messages() -> None:
    payload = {
        "messages": [
            {"role": "user", "content": "q"},
            {"type": "ai", "content": "done with file.pdf"},
        ]
    }
    assert "file.pdf" in _final_assistant_text(payload)


def test_build_user_message_lists_attachments(tmp_path: Path) -> None:
    src = tmp_path / "a.pdf"
    src.write_text("x", encoding="utf-8")
    ws = RunWorkspace(
        root=tmp_path,
        inputs=(
            WorkspaceInput(
                name="a.pdf",
                relative_path="a.pdf",
                source_path=str(src),
                size_bytes=1,
            ),
        ),
    )
    text = _build_user_message("Convert this", ws)
    assert "Convert this" in text
    assert "a.pdf" in text


def test_run_deep_agent_with_injected_agent(tmp_path: Path, monkeypatch) -> None:
    upload = tmp_path / "uploads"
    upload.mkdir()
    src = upload / "work.txt"
    src.write_text("source", encoding="utf-8")

    class _Agent:
        def invoke(self, _payload):
            out = Path(self.root) / "work.pdf"
            out.write_bytes(b"%PDF-1.4 harness")
            return {
                "messages": [
                    SimpleNamespace(type="ai", content="Saved work.pdf"),
                ]
            }

    def _fake_workspace(**kwargs):
        root = tmp_path / "ws" / str(uuid4())
        root.mkdir(parents=True)
        staged = root / "work.txt"
        staged.write_text("source", encoding="utf-8")
        agent = _Agent()
        agent.root = str(root)
        return RunWorkspace(
            root=root,
            inputs=(
                WorkspaceInput(
                    name="work.txt",
                    relative_path="work.txt",
                    source_path=str(src.resolve()),
                    size_bytes=staged.stat().st_size,
                ),
            ),
        )

    monkeypatch.setattr(
        "api.app.agent.harness.create_run_workspace",
        _fake_workspace,
    )

    # Capture workspace root used by promote via agent.invoke side effect
    captured: dict = {}

    class _Agent2:
        def invoke(self, payload):
            # Find workspace from message paths is hard; write beside staged file
            # by scanning tmp workspaces created above — use last ws dir.
            roots = list((tmp_path / "ws").iterdir())
            root = roots[-1]
            out = root / "work.pdf"
            out.write_bytes(b"%PDF-1.4 harness")
            captured["root"] = root
            return {
                "messages": [
                    {"type": "ai", "content": "Saved work.pdf in the workspace"},
                ]
            }

    result = run_deep_agent(
        client_id=str(DEMO_TENANT_ID),
        question="Save this Word document as a PDF",
        attachments=[
            {
                "filename": "work.txt",
                "local_path": str(src),
            }
        ],
        extra={
            "harness_agent": _Agent2(),
            "include_trace": True,
            "run_key": str(uuid4()),
        },
    )
    assert result.extra["phase"] == "harness"
    assert result.extra["workflow"] == "deep_agents"
    assert result.message
    # Delivered when promotion finds the new PDF next to the upload.
    assert any(Path(p).name == "work.pdf" for p in result.extra.get("delivered_files") or [])
