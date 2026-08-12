"""JobQueue product isolation (Sprint 38.3)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from api.app.settings import Settings

_REPO = Path(__file__).resolve().parents[2]
_APP = _REPO / "api" / "app"

# Product enqueue must talk JobQueue — Celery apply_async stays in the adapter.
_FORBIDDEN = re.compile(
    r"\b(apply_async|AsyncResult|celery\.|from celery|import celery)\b",
)

_PRODUCT_ENQUEUE = (
    _APP / "jobs" / "routes.py",
    _APP / "uploads" / "routes.py",
    _APP / "workflows" / "library.py",
)


def _imports_worker_tasks(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "worker.tasks" or alias.name.startswith("worker.tasks."):
                    return alias.name
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "worker.tasks" or node.module.startswith("worker.tasks."):
                return node.module
    return None


def test_product_enqueue_has_no_celery_calls():
    for path in _PRODUCT_ENQUEUE:
        text = path.read_text(encoding="utf-8")
        hit = _FORBIDDEN.search(text)
        assert hit is None, f"{path.name} mentions {hit.group(0)!r}"


def test_product_enqueue_does_not_import_worker_tasks():
    for path in _PRODUCT_ENQUEUE:
        hit = _imports_worker_tasks(path)
        assert hit is None, f"{path.name} imports {hit!r}"


def test_product_enqueue_uses_job_queue():
    for path in _PRODUCT_ENQUEUE:
        text = path.read_text(encoding="utf-8")
        assert "get_job_queue" in text, f"{path.name} missing get_job_queue"
        assert ".enqueue(" in text, f"{path.name} missing .enqueue("


def test_celery_apply_async_only_in_adapter():
    adapter = (_APP / "job_queue" / "celery_adapter.py").read_text(encoding="utf-8")
    assert "apply_async" in adapter
    assert "CeleryJobQueue" in adapter


def test_demo_default_is_celery_and_redis_url_unchanged():
    s = Settings()
    assert s.job_queue == "celery"
    assert "redis_url" in type(s).model_fields
    assert s.redis_url  # broker key stays REDIS_URL
