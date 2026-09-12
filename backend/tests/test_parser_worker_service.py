"""Exercise service lifecycle without Google credentials or queue mutations."""
import importlib.util
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "worker_service", ROOT / "scripts/run_parser_worker_service.py"
)
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "invalid"])
def test_invalid_poll_interval(monkeypatch, value):
    monkeypatch.setenv("PARSER_WORKER_POLL_INTERVAL_SECONDS", value)
    with pytest.raises(ValueError):
        service.settings()


def test_default_configuration(monkeypatch):
    for name in ("PARSER_WORKER_ID", "PARSER_WORKER_POLL_INTERVAL_SECONDS", "PARSER_WORKER_LEASE_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    identity, poll, lease = service.settings()
    assert identity
    assert (poll, lease) == (5, 900)


def test_poll_failure_is_private_and_next_poll_runs(capsys):
    stop = threading.Event()

    class Worker:
        calls = 0

        def run_once(self):
            self.calls += 1
            print("private resume and token")
            if self.calls == 1:
                raise RuntimeError("secret credential")
            stop.set()
            return 1

    worker = Worker()
    service.serve(worker, 0, stop)
    output = capsys.readouterr()
    assert worker.calls == 2
    assert output.err == ""
    assert output.out.splitlines() == [
        "[PARSER_WORKER_SERVICE] started",
        "[PARSER_WORKER_SERVICE] poll_failed",
        "[PARSER_WORKER_SERVICE] attempts_processed",
        "[PARSER_WORKER_SERVICE] stopped",
    ]


def test_duplicate_launcher_exits_before_imports(monkeypatch, tmp_path, capsys):
    lock_path = tmp_path / "worker.lock"
    monkeypatch.setattr(service, "LOCK_FILE", lock_path)
    monkeypatch.setattr(service.signal, "signal", lambda *args: None)
    with lock_path.open("a") as lock:
        service.fcntl.flock(lock, service.fcntl.LOCK_EX | service.fcntl.LOCK_NB)
        assert service.main() == 1
    assert "already_running" in capsys.readouterr().out


def test_startup_error_does_not_log_exception(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(service, "LOCK_FILE", tmp_path / "missing" / "worker.lock")
    monkeypatch.setattr(service.signal, "signal", lambda *args: None)
    assert service.main() == 1
    output = capsys.readouterr()
    assert output.out == "[PARSER_WORKER_SERVICE] startup_or_runtime_failed\n"
    assert output.err == ""


def test_process_stop_crash_and_lock_recovery(tmp_path):
    import os
    import signal
    import subprocess
    import sys

    # Inject only the #365 public interface; no Google access or parser semantics.
    program = '''
import importlib.util, sys, types
from pathlib import Path
spec = importlib.util.spec_from_file_location("launcher", sys.argv[1])
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
launcher.LOCK_FILE = Path(sys.argv[2])
sys.modules["config"] = types.ModuleType("config")
worker = types.ModuleType("services.parser_worker")
worker.ParserWorkerConfig = lambda **kwargs: kwargs
class Worker:
    def __init__(self, config): pass
    def run_once(self): return 0
worker.ParserWorker = Worker
sys.modules["services.parser_worker"] = worker
raise SystemExit(launcher.main())
'''
    command = [sys.executable, "-u", "-c", program,
               str(ROOT / "scripts/run_parser_worker_service.py"), str(tmp_path / "worker.lock")]
    environment = {"PATH": os.environ.get("PATH", ""), "PARSER_WORKER_POLL_INTERVAL_SECONDS": "0.01"}
    processes = []

    def start():
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=environment)
        processes.append(process)
        # Bound startup observation without blocking indefinitely on readline.
        import select
        assert select.select([process.stdout], [], [], 5)[0]
        assert process.stdout.readline().strip() == "[PARSER_WORKER_SERVICE] started"
        return process

    try:
        first = start()
        duplicate = subprocess.run(command, capture_output=True, text=True,
                                   env=environment, timeout=5)
        assert duplicate.returncode == 1
        assert "already_running" in duplicate.stdout
        first.send_signal(signal.SIGTERM)
        stdout, stderr = first.communicate(timeout=5)
        assert first.returncode == 0
        assert "stopped" in stdout
        assert not stderr
        second = start()
        second.kill()
        second.communicate(timeout=5)
        assert second.returncode == -signal.SIGKILL
        third = start()
        third.terminate()
        third.communicate(timeout=5)
        assert third.returncode == 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)


def test_launcher_constructs_real_worker_and_polls(monkeypatch, tmp_path, capsys):
    from services import parser_worker

    handlers = {}
    configs = []
    original_serve = service.serve

    def run_service(worker, poll, stop):
        assert isinstance(worker, parser_worker.ParserWorker)
        configs.append(worker.config)
        original_serve(worker, poll, stop)

    def list_jobs(limit):
        assert limit == 1
        # Simulate systemd SIGTERM arriving during the real polling operation.
        handlers[service.signal.SIGTERM]()
        return []

    monkeypatch.setattr(service, "LOCK_FILE", tmp_path / "worker.lock")
    monkeypatch.setattr(service.signal, "signal", lambda sig, fn: handlers.update({sig: fn}))
    monkeypatch.setattr(service, "serve", run_service)
    monkeypatch.setattr(parser_worker, "list_claimable_jobs", list_jobs)
    monkeypatch.setenv("PARSER_WORKER_ID", "staging-test-worker")
    monkeypatch.setenv("PARSER_WORKER_POLL_INTERVAL_SECONDS", "0.01")
    monkeypatch.setenv("PARSER_WORKER_LEASE_SECONDS", "120")
    assert service.main() == 0
    assert configs == [parser_worker.ParserWorkerConfig(
        worker_id="staging-test-worker", poll_interval_seconds=0.01, lease_seconds=120,
    )]
    output = capsys.readouterr()
    assert output.out.splitlines() == [
        "[PARSER_WORKER_SERVICE] started", "[PARSER_WORKER_SERVICE] stopped",
    ]
    assert output.err == ""


def test_service_preserves_real_worker_retry_and_private_errors(monkeypatch, capsys):
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from services import parser_worker

    stop = threading.Event()
    job = {
        "job_id": "synthetic-job", "submission_id": "synthetic-submission",
        "drive_file_id": "private-drive-id", "status": "running",
        "locked_by": "test-worker", "last_parser_run_id": "test-run",
        "lock_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "attempt_count": "1", "max_attempts": "3",
    }
    errors = []

    def update(job_id, fields):
        job.update(fields)
        if fields.get("status") == "retry_scheduled":
            stop.set()
        return job

    def download(file_id):
        print("private resume text")
        raise RuntimeError("private token")

    monkeypatch.setattr(parser_worker, "list_claimable_jobs", lambda limit: [job])
    monkeypatch.setattr(parser_worker, "claim_job", lambda **kw: SimpleNamespace(claimed=True, job=job))
    monkeypatch.setattr(parser_worker, "get_job", lambda job_id: job)
    monkeypatch.setattr(parser_worker, "update_job", update)
    monkeypatch.setattr(parser_worker, "download_file", download)
    monkeypatch.setattr(parser_worker, "append_error_row", lambda **kw: errors.append(kw))
    worker = parser_worker.ParserWorker(
        parser_worker.ParserWorkerConfig(worker_id="test-worker"),
        parser_run_id_factory=lambda: "test-run",
    )
    # Bound the test if retry handling regresses.
    timer = threading.Timer(2, stop.set)
    timer.start()
    try:
        service.serve(worker, 0.01, stop)
    finally:
        timer.cancel()
    assert job["status"] == "retry_scheduled"
    assert job["attempt_count"] == "1"
    assert job["last_parser_run_id"] == "test-run"
    assert errors[0]["error_code"] == "PARSER_FAILED"
    output = capsys.readouterr()
    assert "private" not in output.out + output.err
