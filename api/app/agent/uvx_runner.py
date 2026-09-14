"""CLI argument helpers shared by outcome verification.

The old subprocess ``uvx`` invoke path was removed with the legacy tool runner.
This module keeps only output-directory inference used by the harness verifier.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

_OUTPUT_DIR_FLAGS = frozenset({"--output-dir", "-d", "--outdir"})


def infer_output_dir_from_args(
    args_list: Sequence[str],
    *,
    cwd: str | Path | None = None,
) -> Path | None:
    """Return a declared output directory from common CLI flags, if any."""
    args = [str(x) for x in args_list]
    idx = 0
    while idx < len(args):
        token = args[idx]
        for flag in _OUTPUT_DIR_FLAGS:
            if token == flag:
                if idx + 1 < len(args):
                    raw = args[idx + 1].strip()
                    if raw:
                        path = Path(raw)
                        if not path.is_absolute() and cwd:
                            path = Path(cwd) / path
                        return path.resolve()
                return None
            prefix = f"{flag}="
            if token.startswith(prefix):
                raw = token[len(prefix) :].strip()
                if raw:
                    path = Path(raw)
                    if not path.is_absolute() and cwd:
                        path = Path(cwd) / path
                    return path.resolve()
        idx += 1
    return None
