from __future__ import annotations

from rq import SimpleWorker

from back.api import repository
from back.api.config import QUEUE_NAME
from back.worker.queue import get_redis


def main() -> None:
    repository.init_db()
    worker = SimpleWorker([QUEUE_NAME], connection=get_redis())
    worker.work()


if __name__ == "__main__":
    main()
