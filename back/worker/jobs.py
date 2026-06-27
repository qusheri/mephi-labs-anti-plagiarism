from __future__ import annotations

import asyncio

from back.worker.check_processor import process_check


def process_check_job(task_id: str) -> None:
    asyncio.run(process_check(task_id))
