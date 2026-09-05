"""Host-boundary policy for executed actions.

Keeps tenant secrets out of child processes. Network jails and OS containers
are out of scope here; this is the portable edge of the sandbox contract.
"""

from __future__ import annotations

import os
from typing import Any

# Role-named markers, not vendor names. A key matching these is withheld
# from model-authored processes even when it is present on the host.
_SECRET_MARKERS = (
    "API_KEY",
    "SECRET",
    "PASSWORD",
    "PRIVATE_KEY",
    "ACCESS_TOKEN",
    "AUTH_TOKEN",
    "CREDENTIAL",
)


def child_environment(settings: Any | None = None) -> dict[str, str]:
    """Environment for a workspace subprocess.

    Copies the host environment, then drops variables whose names look like
    secrets. PATH and other process-launch keys stay so ``uvx`` can run.
    """
    env = os.environ.copy()
    scrub = True
    if settings is not None:
        scrub = bool(getattr(settings, "executor_scrub_child_env", True))
    if not scrub:
        return env
    for key in list(env):
        upper = key.upper()
        if any(marker in upper for marker in _SECRET_MARKERS):
            env.pop(key, None)
    return env
