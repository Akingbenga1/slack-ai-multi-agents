"""Product agent result contract.

``AgentResult`` is the shared outcome shape for ``plan_and_execute`` /
harness runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Output of a harness run. Details stay in ``extra``."""

    role: str
    client_id: str
    status: str
    message: str
    extra: dict[str, Any] = field(default_factory=dict)
