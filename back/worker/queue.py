from __future__ import annotations

from redis import Redis
from rq import Queue

from back.api.config import QUEUE_NAME, REDIS_URL
from back.worker.jobs import process_check_job


def get_redis() -> Redis:
    return Redis.from_url(REDIS_URL)


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis())


def enqueue_check(task_id: str) -> str:
    job = get_queue().enqueue(process_check_job, task_id, job_timeout="30m")
    return job.id
