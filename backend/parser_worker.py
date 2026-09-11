"""Command-line entrypoint for the durable parser worker."""
from __future__ import annotations

import os
import socket

from services.parser_worker import ParserWorker, ParserWorkerConfig


def main() -> None:
    worker_id = os.getenv("PARSER_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    poll_interval = float(os.getenv("PARSER_WORKER_POLL_INTERVAL_SECONDS", "5"))
    lease_seconds = int(os.getenv("PARSER_WORKER_LEASE_SECONDS", "900"))

    worker = ParserWorker(
        ParserWorkerConfig(
            worker_id=worker_id,
            poll_interval_seconds=poll_interval,
            lease_seconds=lease_seconds,
        )
    )
    print(f"[PARSER_WORKER] Started worker_id={worker_id}")
    worker.poll_forever()


if __name__ == "__main__":
    main()
