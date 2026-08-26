"""Normalize CLI discovery hits to tool_registry-compatible config shape."""

from __future__ import annotations

import re
from typing import Any

from api.app.discovery.base import DiscoveredTool


def parse_tldr_examples(body: str) -> list[dict[str, str]]:
    """Extract ``{purpose, usage}`` pairs from a tldr markdown page body."""
    examples: list[dict[str, str]] = []
    purpose = ""
    for raw in (body or "").splitlines():
        line = raw.strip()
        if line.startswith("- "):
            purpose = line[2:].rstrip(":").strip()
            continue
        if line.startswith("`") and line.endswith("`") and len(line) > 2:
            usage = line[1:-1].strip()
            if usage:
                examples.append(
                    {
                        "purpose": purpose or usage,
                        "usage": usage,
                    }
                )
            purpose = ""
    return examples


def _slugify(text: str, *, fallback: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or fallback
    key = base
    n = 2
    while key in used:
        key = f"{base}-{n}"
        n += 1
    used.add(key)
    return key


def examples_to_subcommands(examples: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Turn example rows into ``config.subcommands`` keyed like tool_registry."""
    used: set[str] = set()
    out: dict[str, dict[str, str]] = {}
    for i, row in enumerate(examples):
        if not isinstance(row, dict):
            continue
        purpose = str(
            row.get("purpose") or row.get("description") or row.get("summary") or ""
        ).strip()
        usage = str(
            row.get("usage") or row.get("command") or row.get("template") or ""
        ).strip()
        if not usage and not purpose:
            continue
        if not usage:
            usage = purpose
        if not purpose:
            purpose = usage
        first_token = usage.split()[0] if usage.split() else f"cmd-{i + 1}"
        key_source = purpose if purpose != usage else first_token
        key = _slugify(key_source, fallback=f"cmd-{i + 1}", used=used)
        out[key] = {"purpose": purpose, "usage": usage}
    return out


def build_cli_config(
    *,
    command: str,
    examples: list[dict[str, Any]] | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a tool_registry-aligned CLI ``config`` object."""
    config: dict[str, Any] = {}
    if isinstance(existing, dict):
        config.update(existing)

    cmd = str(config.get("command") or command or "").strip() or command
    config["command"] = cmd

    if "args" not in config or config.get("args") is None:
        config["args"] = []
    elif not isinstance(config["args"], list):
        config["args"] = [config["args"]]

    subcommands = config.get("subcommands")
    if not isinstance(subcommands, dict) or not subcommands:
        config["subcommands"] = examples_to_subcommands(examples or [])
    else:
        # Normalize each entry to purpose/usage keywords.
        normalized: dict[str, dict[str, str]] = {}
        used: set[str] = set()
        for raw_key, raw_val in subcommands.items():
            key = _slugify(str(raw_key), fallback="cmd", used=used)
            if isinstance(raw_val, dict):
                purpose = str(
                    raw_val.get("purpose")
                    or raw_val.get("description")
                    or raw_val.get("summary")
                    or ""
                ).strip()
                usage = str(
                    raw_val.get("usage")
                    or raw_val.get("command")
                    or raw_val.get("template")
                    or ""
                ).strip()
            else:
                purpose = str(raw_val).strip()
                usage = purpose
            if not purpose and not usage:
                continue
            normalized[key] = {
                "purpose": purpose or usage,
                "usage": usage or purpose,
            }
        config["subcommands"] = normalized

    return config


def normalize_cli_discovered_tool(tool: DiscoveredTool) -> DiscoveredTool:
    """Ensure every CLI discovery hit exposes registry-compatible ``config``."""
    if tool.kind != "cli":
        return tool

    meta = dict(tool.metadata or {})
    examples_raw = meta.get("examples")
    examples: list[dict[str, Any]] = []
    if isinstance(examples_raw, list):
        for item in examples_raw:
            if isinstance(item, dict):
                examples.append(item)
            elif isinstance(item, str) and item.strip():
                examples.append({"purpose": item.strip(), "usage": item.strip()})

    existing_config = meta.get("config") if isinstance(meta.get("config"), dict) else None
    # Prefer explicit tool.config if present on the dataclass (added field).
    tool_config = getattr(tool, "config", None)
    if isinstance(tool_config, dict) and tool_config:
        existing_config = tool_config

    config = build_cli_config(
        command=tool.name,
        examples=examples,
        existing=existing_config,
    )

    # Keep examples as purpose/usage list for clients that read metadata.
    if config.get("subcommands"):
        meta["examples"] = [
            {"purpose": v["purpose"], "usage": v["usage"]}
            for v in config["subcommands"].values()
        ]
    meta.pop("config", None)

    return DiscoveredTool(
        id=tool.id,
        name=tool.name,
        summary=tool.summary,
        source=tool.source,
        kind=tool.kind,
        metadata=meta,
        config=config,
    )
