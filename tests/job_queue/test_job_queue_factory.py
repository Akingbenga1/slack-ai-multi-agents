"""JobQueue factory + Celery adapter smoke (Sprint 38.1)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.app.job_queue import CeleryJobQueue, EnqueueResult, get_job_queue
from api.app.settings import Settings
from worker.job_meta import KIND_HEARTBEAT


def test_factory_defaults_to_celery():
    queue = get_job_queue(Settings(job_queue="celery"))
    assert isinstance(queue, CeleryJobQueue)
    assert queue.name == "celery"


def test_factory_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown JOB_QUEUE"):
        get_job_queue(Settings(job_queue="sqs"))


def test_factory_rq_not_implemented():
    with pytest.raises(ValueError, match="rq"):
        get_job_queue(Settings(job_queue="rq"))


def test_enqueue_requires_tenant_id():
    queue = CeleryJobQueue(Settings(job_queue="celery"))
    with pytest.raises(ValueError, match="tenant_id is required"):
        queue.enqueue(kind=KIND_HEARTBEAT, tenant_id="", payload={})


def test_enqueue_unknown_kind():
    queue = CeleryJobQueue(Settings(job_queue="celery"))
    with pytest.raises(ValueError, match="Unknown job kind"):
        queue.enqueue(kind="not_a_kind", tenant_id=str(uuid4()), payload={})


def test_enqueue_result_id_alias():
    result = EnqueueResult(task_id="abc", queue="default", kind=KIND_HEARTBEAT)
    assert result.id == "abc"
    assert result.task_id == "abc"


def test_demo_default_is_celery():
    assert Settings().job_queue == "celery"
