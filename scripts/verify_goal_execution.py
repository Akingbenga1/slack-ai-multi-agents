"""Live end-to-end check for one plain-English goal.

Runs the full orchestrator -> executor -> uvx path against the real database
and LLM, then reports whether the outcome was verified. Usage:

    python -m scripts.verify_goal_execution "<request>" [input filename ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from api.app.agent.facade import plan_and_execute

CLIENT_ID = "11111111-1111-1111-1111-111111111111"
UPLOAD_DIR = Path("data/uploads") / CLIENT_ID


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else (
        "Combine the 4 png files into one single png image file"
    )
    names = sys.argv[2:] or ["dryrun_a.png", "dryrun_b.png", "dryrun_c.png", "dryrun_d.png"]
    attachments = []
    for name in names:
        path = (UPLOAD_DIR / name).resolve()
        if not path.is_file():
            print(f"missing input: {path}")
            return 2
        attachments.append(
            {
                "filename": name.replace("dryrun_", ""),
                "upload_id": "verify",
                "local_path": str(path),
            }
        )

    result = plan_and_execute(
        client_id=CLIENT_ID,
        question=question,
        attachments=attachments,
        extra={"include_trace": True},
    )

    print("=" * 70)
    print(f"status : {result.status}")
    print(f"message:\n{result.message}")
    extra = result.extra or {}
    steps = extra.get("plan_steps") or []
    print(f"\nplanned steps: {len(steps)}")
    for step in steps:
        print(json.dumps(step, default=str)[:400])
    for key in ("workspace", "run_id", "plan_id"):
        if extra.get(key):
            print(f"{key}: {extra[key]}")
    print("=" * 70)
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
