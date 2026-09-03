"""Isolated execution workspaces for agent runs.

A run workspace is the only directory an executing step may read or write.
Declared inputs are copied in, so originals are preserved structurally rather
than by instructing the model not to touch them, and anything that appears
during a step is attributable to that step. Names are normalised to
forward-slash relative paths so invocations stay portable across hosts.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from api.app.logging_config import get_logger

logger = get_logger("api.agent.workspace")

# Reserved subtree for loop-owned files (scripts, captured output). Never
# reported as a produced artifact.
INTERNAL_DIRNAME = ".agent"
SCRIPTS_DIRNAME = "scripts"

_UNSAFE_NAME_CHARS = re.compile(r"[^A-Za-z0-9._+-]+")
_LEADING_JUNK = re.compile(r"^[-.]+")

# Ceiling for a full absolute path, kept below the 260-character limit Windows
# enforces without long-path support. Workspace roots already carry two ids, and
# file names are derived from model-written labels, so the label is the part
# that has to yield.
_MAX_ABSOLUTE_PATH = 250
_MIN_TRIMMED_NAME = 8


def safe_component(raw: Any, *, fallback: str = "input") -> str:
    """Normalise one path component to a portable, flag-safe file name."""
    name = Path(str(raw or "")).name
    name = _UNSAFE_NAME_CHARS.sub("_", name).strip("_")
    name = _LEADING_JUNK.sub("", name)
    if not name:
        return fallback
    return name[:120]


def fit_name_to_path_budget(
    directory: Path, *, prefix: str, name: str, suffix: str
) -> str:
    """Shorten ``name`` so ``directory/prefix+name+suffix`` stays writable.

    The sequence prefix and extension are preserved, so a trimmed file remains
    identifiable even when the label it came from was long.
    """
    fixed = len(str(directory)) + 1 + len(prefix) + len(suffix)
    room = _MAX_ABSOLUTE_PATH - fixed
    if room >= len(name):
        return name
    return name[: max(_MIN_TRIMMED_NAME, room)]


@dataclass(frozen=True)
class WorkspaceInput:
    """One declared input, as the model will see and address it."""

    name: str
    relative_path: str
    source_path: str
    size_bytes: int

    @property
    def suffix(self) -> str:
        return Path(self.relative_path).suffix.lower()


@dataclass
class RunWorkspace:
    """Root directory plus the inputs staged inside it."""

    root: Path
    inputs: tuple[WorkspaceInput, ...] = ()
    _script_seq: int = field(default=0, repr=False)

    @property
    def scripts_dir(self) -> Path:
        return self.root / INTERNAL_DIRNAME / SCRIPTS_DIRNAME

    @property
    def input_paths(self) -> list[Path]:
        return [self.root / i.relative_path for i in self.inputs]

    def is_internal(self, path: Path) -> bool:
        try:
            rel = path.resolve().relative_to(self.root)
        except (ValueError, OSError):
            return False
        return rel.parts[:1] == (INTERNAL_DIRNAME,)

    def resolve_within(self, relative: str) -> Path | None:
        """Resolve a relative path inside the workspace, or None if it escapes."""
        text = str(relative or "").strip().replace("\\", "/").lstrip("/")
        if not text or text.startswith("~"):
            return None
        candidate = self.root / text
        try:
            resolved = candidate.resolve()
            resolved.relative_to(self.root)
        except (ValueError, OSError):
            return None
        return resolved

    def relative_of(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except (ValueError, OSError):
            return str(path).replace("\\", "/")

    def next_script_path(self, label: str) -> Path:
        self._script_seq += 1
        prefix = f"{self._script_seq:02d}_"
        name = safe_component(label, fallback="action") or "action"
        name = fit_name_to_path_budget(
            self.scripts_dir, prefix=prefix, name=name, suffix=".py"
        )
        target = self.scripts_dir / f"{prefix}{name}.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def snapshot(self) -> dict[Path, float]:
        """Modification times of every non-internal file, for step baselines."""
        found: dict[Path, float] = {}
        if not self.root.is_dir():
            return found
        for entry in self.root.rglob("*"):
            if not entry.is_file() or self.is_internal(entry):
                continue
            try:
                found[entry.resolve()] = entry.stat().st_mtime
            except OSError:
                continue
        return found

    def files_since(self, baseline: dict[Path, float]) -> list[Path]:
        """Files created or modified since ``baseline`` (produced artifacts)."""
        changed: list[Path] = []
        for path, mtime in self.snapshot().items():
            previous = baseline.get(path)
            if previous is None or mtime > previous:
                changed.append(path)
        return sorted(changed)

    def listing(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """Compact listing of workspace contents for model grounding."""
        entries: list[dict[str, Any]] = []
        if not self.root.is_dir():
            return entries
        input_paths = {p.resolve() for p in self.input_paths if p.exists()}
        for entry in sorted(self.root.rglob("*")):
            if not entry.is_file() or self.is_internal(entry):
                continue
            try:
                stat = entry.stat()
                resolved = entry.resolve()
            except OSError:
                continue
            entries.append(
                {
                    "path": self.relative_of(entry),
                    "bytes": stat.st_size,
                    "kind": "input" if resolved in input_paths else "produced",
                }
            )
            if len(entries) >= limit:
                break
        return entries

    def input_block(self) -> str:
        """Model-facing description of the staged inputs."""
        if not self.inputs:
            return "(none)"
        return "\n".join(
            f"- {item.relative_path} ({item.size_bytes} bytes, original name {item.name!r})"
            for item in self.inputs
        )


def _unique_relative_name(used: set[str], desired: str) -> str:
    if desired not in used:
        used.add(desired)
        return desired
    stem = Path(desired).stem
    suffix = Path(desired).suffix
    index = 2
    while f"{stem}_{index}{suffix}" in used:
        index += 1
    final = f"{stem}_{index}{suffix}"
    used.add(final)
    return final


def _attachment_source(attachment: dict[str, Any]) -> Path | None:
    for key in ("local_path", "path", "file_path"):
        raw = str(attachment.get(key) or "").strip()
        if not raw:
            continue
        candidate = Path(raw)
        if candidate.is_file():
            return candidate
    return None


def workspace_root(settings: Any = None) -> Path:
    """Base directory holding all run workspaces."""
    if settings is None:
        from api.app.settings import get_settings

        settings = get_settings()
    raw = str(getattr(settings, "agent_workspace_root", "") or "data/workspaces")
    root = Path(raw)
    if not root.is_absolute():
        root = Path.cwd() / root
    return root


def create_run_workspace(
    *,
    client_id: str,
    run_key: str,
    attachments: Sequence[dict[str, Any]] | None = None,
    settings: Any = None,
    base_dir: str | Path | None = None,
) -> RunWorkspace:
    """Create an isolated workspace and stage declared inputs inside it."""
    base = Path(base_dir) if base_dir is not None else workspace_root(settings)
    root = base / safe_component(client_id, fallback="tenant") / safe_component(
        run_key, fallback="run"
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / INTERNAL_DIRNAME / SCRIPTS_DIRNAME).mkdir(parents=True, exist_ok=True)

    staged: list[WorkspaceInput] = []
    used: set[str] = set()
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        source = _attachment_source(attachment)
        if source is None:
            continue
        display = str(attachment.get("filename") or source.name)
        desired = safe_component(display, fallback=safe_component(source.name))
        relative = _unique_relative_name(used, desired)
        target = root / relative
        try:
            shutil.copy2(source, target)
        except OSError:
            logger.warning(
                "workspace_input_copy_failed source=%s target=%s", source, target
            )
            continue
        staged.append(
            WorkspaceInput(
                name=display,
                relative_path=relative,
                source_path=str(source.resolve()),
                size_bytes=target.stat().st_size,
            )
        )

    logger.info(
        "workspace_created root=%s inputs=%d", root, len(staged)
    )
    return RunWorkspace(root=root.resolve(), inputs=tuple(staged))


def promote_outputs(
    workspace: RunWorkspace,
    *,
    destination: str | Path,
    paths: Iterable[Path] | None = None,
) -> list[str]:
    """Copy produced artifacts out of the workspace into durable storage."""
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    input_paths = {p.resolve() for p in workspace.input_paths if p.exists()}
    candidates = (
        list(paths)
        if paths is not None
        else [p for p in workspace.snapshot() if p not in input_paths]
    )
    promoted: list[str] = []
    used: set[str] = {p.name for p in dest.iterdir() if p.is_file()}
    for path in candidates:
        if not path.is_file() or workspace.is_internal(path):
            continue
        if path.resolve() in input_paths:
            continue
        name = _unique_relative_name(used, safe_component(path.name))
        target = dest / name
        try:
            shutil.copy2(path, target)
        except OSError:
            logger.warning("workspace_output_promote_failed source=%s", path)
            continue
        promoted.append(str(target.resolve()))
    return promoted


def cleanup_workspace(workspace: RunWorkspace, *, keep: bool | None = None) -> None:
    """Remove a workspace unless retention is requested for tracing."""
    if keep is None:
        from api.app.settings import get_settings

        keep = bool(getattr(get_settings(), "agent_workspace_keep", True))
    if keep:
        return
    shutil.rmtree(workspace.root, ignore_errors=True)
