"""CLI dry-run for the Deep Agents harness (no Slack post).

Examples:
  uv run python scripts/agent_dry_run.py \
    --client-id 11111111-1111-1111-1111-111111111111 \
    --question "onboarding checklist for new hires"
"""

from __future__ import annotations

import argparse
import json
import sys

from api.app.agent.facade import plan_and_execute


def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrator → executor dry-run")
    parser.add_argument("--client-id", required=True, help="Tenant UUID")
    parser.add_argument("--question", required=True, help="User question")
    parser.add_argument(
        "--conversation-id",
        default="cli",
        help="Thread / conversation key (default: cli)",
    )
    args = parser.parse_args()

    try:
        result = plan_and_execute(
            client_id=args.client_id,
            question=args.question,
            conversation_id=args.conversation_id,
        )
    except Exception as exc:
        print(f"agent_dry_run_failed: {exc}", file=sys.stderr)
        return 1

    workflow = result.extra.get("workflow") or "qa"
    plan_id = result.extra.get("plan_id")
    print(
        f"agent_dry_run_ok status={result.status} workflow={workflow} "
        f"plan_id={plan_id}"
    )
    print(f"answer: {result.message}")
    print(json.dumps(result.extra, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
