"""Command-line entrypoint for the durable parser worker."""
from __future__ import annotations

import contextlib
import os
import socket


def main() -> int:
    try:
        # Imports and schema access may emit sensitive configuration diagnostics.
        with open(os.devnull, "w") as sink:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                from validator import validate_sheet_schema
                validate_sheet_schema()
                from services.parser_worker import ParserWorker, ParserWorkerConfig
    except Exception:
        print("[PARSER_WORKER] Schema startup failed")
        return 1

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
