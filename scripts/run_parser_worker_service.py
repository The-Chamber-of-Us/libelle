#!/usr/bin/env python3
"""Private systemd launcher for the #365 worker; never changes queue semantics."""
from __future__ import annotations

import contextlib
import fcntl
import math
import os
from pathlib import Path
import signal
import socket
import sys
import threading

BACKEND = Path(__file__).resolve().parents[1] / "backend"
LOCK_FILE = Path("/var/lib/libelle-parser-worker/worker.lock")


def emit(event: str) -> None:
    print(f"[PARSER_WORKER_SERVICE] {event}", flush=True)


def settings() -> tuple[str, float, int]:
    identity = os.getenv("PARSER_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    poll = float(os.getenv("PARSER_WORKER_POLL_INTERVAL_SECONDS", "5"))
    lease = int(os.getenv("PARSER_WORKER_LEASE_SECONDS", "900"))
    if not math.isfinite(poll) or poll <= 0 or lease <= 0 or not identity.strip():
        raise ValueError("Invalid worker settings")
    return identity, poll, lease


def serve(worker, poll: float, stop: threading.Event) -> None:
    emit("started")
    while not stop.is_set():
        try:
            # Legacy parser/Google code can print input or exception details.
            # Keep those streams out of journald; durable error writes are unchanged.
            with open(os.devnull, "w") as sink:
                with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    processed = worker.run_once()
            if processed:
                emit("attempts_processed")
        except Exception:
            emit("poll_failed")
        stop.wait(poll)
    emit("stopped")


def main() -> int:
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    sys.path.insert(0, str(BACKEND))
    try:
        # Persistent inode: never unlink this file, including during restarts.
        # A second cooperating launcher on this host must fail before imports/polling.
        with LOCK_FILE.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                emit("already_running")
                return 1
            with open(os.devnull, "w") as sink:
                with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    import config  # noqa: F401 - load the backend dotenv convention first
                    identity, poll, lease = settings()
                    from services.parser_worker import ParserWorker, ParserWorkerConfig
                    worker = ParserWorker(ParserWorkerConfig(
                        worker_id=identity,
                        poll_interval_seconds=poll,
                        lease_seconds=lease,
                    ))
            serve(worker, poll, stop)
    except Exception:
        # Do not print exception values: credential loaders may include secrets.
        emit("startup_or_runtime_failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
