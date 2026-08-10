"""Sprint 13 — CLI dry-run for LangGraph agent (no Slack post).

Examples:
  uv run python scripts/agent_dry_run.py \\
    --client-id 11111111-1111-1111-1111-111111111111 \\
    --question "onboarding checklist for new hires"

  # Force memory checkpointer + stub LLM (no Postgres / Anthropic)
  AGENT_CHECKPOINTER=memory uv run python scripts/agent_dry_run.py \\
    --client-id 11111111-1111-1111-1111-111111111111 \\
    --question "refund policy" --memory --no-usage
"""

from __future__ import annotations

import argparse
import json
import sys

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.run import run_agent
from api.app.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="LangGraph agent dry-run")
    parser.add_argument("--client-id", required=True, help="Tenant UUID")
    parser.add_argument("--question", required=True, help="User question")
    parser.add_argument(
        "--conversation-id",
        default="cli",
        help="Thread / conversation key (default: cli)",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="Use MemorySaver instead of Postgres checkpointer",
    )
    parser.add_argument(
        "--no-usage",
        action="store_true",
        help="Skip writing llm_tokens usage events",
    )
    args = parser.parse_args()

    settings = get_settings()
    checkpointer = MemorySaver() if args.memory else None
    try:
        result = run_agent(
            client_id=args.client_id,
            question=args.question,
            conversation_id=args.conversation_id,
            settings=settings,
            checkpointer=checkpointer,
            record_usage=not args.no_usage,
        )
    except Exception as exc:
        print(f"agent_dry_run_failed: {exc}", file=sys.stderr)
        return 1

    # Compact CLI summary + full JSON
    print(
        f"agent_dry_run_ok workflow={result['workflow']} "
        f"tier={result['model_tier']} chunks={len(result['retrieved_chunks'])} "
        f"hedge={result['hedge']} tokens={result['usage_tokens']}"
    )
    print(f"answer: {result['answer']}")
    print(json.dumps(
        {
            "thread_id": result["thread_id"],
            "complexity_flags": result["complexity_flags"],
            "chunk_labels": [
                c.get("label") for c in result["retrieved_chunks"]
            ],
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
