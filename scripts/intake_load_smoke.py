#!/usr/bin/env python3
"""Synthetic intake/load smoke test for the v0.3 volunteer pipeline.

This is intentionally separate from parser benchmark scoring. It submits
synthetic-only intake payloads to a running staging/dev backend and verifies the
basic intake pipeline properties maintainers care about under a modest burst.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
DEFAULT_FIXTURE_DIR = BACKEND_DIR / "benchmarks" / "resumes"
DEFAULT_ENDPOINT = "/api/upload"
SYNTHETIC_DOMAIN = "example.test"
PRODUCTION_MARKERS = ("prod", "production", "libelle.io")
PATH_ENV_VARS = ("GOOGLE_CREDENTIALS", "GOOGLE_OAUTH_CLIENT", "TOKEN_FILE")
ANY_MODE = "any"


@dataclass
class SheetSnapshot:
    submissions: list[dict[str, str]]
    parser_results: list[dict[str, str]]
    errors: list[dict[str, str]]


@dataclass
class AttemptResult:
    index: int
    mode: str
    ok: bool
    status_code: int | None
    submission_id: str | None
    code: str | None
    message: str
    elapsed_seconds: float


def _backend_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _json_request(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    request = Request(url, method="GET")
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        payload = json.loads(body) if body else {}
        return response.status, payload


def _post_multipart(
    *,
    url: str,
    fields: dict[str, str],
    file_path: Path | None,
    timeout: float,
) -> tuple[int, dict[str, Any]]:
    boundary = f"----libelle-smoke-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )

    if file_path is not None:
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/pdf"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="file"; '
                    f'filename="{file_path.name}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                file_path.read_bytes(),
                b"\r\n",
            ]
        )

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "User-Agent": "libelle-intake-load-smoke/0.1",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = _decode_json_body(response.read())
            return response.status, payload
    except HTTPError as exc:
        payload = _decode_json_body(exc.read())
        return exc.code, payload


def _decode_json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        decoded = body.decode("utf-8")
        payload = json.loads(decoded)
        return payload if isinstance(payload, dict) else {"body": payload}
    except Exception:
        return {"body": body.decode("utf-8", errors="replace")}


def _synthetic_payload(index: int, run_id: str) -> dict[str, str]:
    padded = f"{index:03d}"
    return {
        "full_name": f"Smoke Test Volunteer {padded}",
        "email": f"intake-smoke-{run_id}-{padded}@{SYNTHETIC_DOMAIN}",
        "location": f"Smoke City {padded}, NY",
        "interests": "intake smoke testing, backend reliability",
        "availability": "2-4 hours per week",
        "experience_level": "Synthetic test profile",
        "linkedin_url": f"https://www.linkedin.com/in/libelle-smoke-{run_id}-{padded}",
        "github_url": f"https://github.com/libelle-smoke-{run_id}-{padded}",
        "motivation": (
            "Synthetic load smoke submission. This is not a real volunteer "
            "application and contains no real resume data."
        ),
        "consent": "true",
    }


def _load_pdf_fixtures(fixture_dir: Path) -> list[Path]:
    return sorted(path for path in fixture_dir.rglob("*.pdf") if path.is_file())


def _load_env_file(env_file: Path | None) -> None:
    if env_file is None:
        return

    env_path = env_file.expanduser().resolve()
    if not env_path.exists():
        raise SystemExit(f"Env file does not exist: {env_path}")

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if not key or key in os.environ:
            continue
        if key in PATH_ENV_VARS and value and not Path(value).is_absolute():
            value = str((env_path.parent / value).resolve())
        os.environ[key] = value


def _take_sheet_snapshot() -> SheetSnapshot:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from storage.sheets_repo import (  # pylint: disable=import-error,import-outside-toplevel
        load_error_rows,
        load_parser_result_rows,
        load_submission_records,
    )

    return SheetSnapshot(
        submissions=list(load_submission_records().values()),
        parser_results=load_parser_result_rows(),
        errors=load_error_rows(),
    )


def _ids_from(rows: list[dict[str, str]]) -> set[str]:
    return {row.get("submission_id", "").strip() for row in rows if row.get("submission_id", "").strip()}


def _quota_or_api_failures(results: list[AttemptResult]) -> list[AttemptResult]:
    markers = ("quota", "rate", "limit", "api", "permission", "forbidden")
    failures: list[AttemptResult] = []
    for result in results:
        text = f"{result.code or ''} {result.message}".lower()
        if result.status_code in {403, 429, 500, 502, 503, 504} or any(m in text for m in markers):
            failures.append(result)
    return failures


def _failure_code(result: AttemptResult) -> str:
    if result.code:
        return result.code
    if result.status_code is not None:
        return f"HTTP_STATUS_{result.status_code}"
    return "UNKNOWN_FAILURE"


def _parse_allowed_failures(raw_values: list[str]) -> set[tuple[str, str]]:
    allowed: set[tuple[str, str]] = set()
    for raw_value in raw_values:
        if ":" not in raw_value:
            raise SystemExit(
                "Allowed failures must use MODE:CODE, such as "
                "no_resume:FILE_REQUIRED or any:VALIDATION_ERROR."
            )

        raw_mode, raw_code = raw_value.split(":", 1)
        mode = raw_mode.strip().lower()
        code = raw_code.strip()
        if mode not in {ANY_MODE, "no_resume", "resume"}:
            raise SystemExit("--allow-failure mode must be one of any, no_resume, or resume.")
        if not code:
            raise SystemExit("--allow-failure code cannot be empty.")
        allowed.add((mode, code))
    return allowed


def _is_allowed_failure(result: AttemptResult, allowed_failures: set[tuple[str, str]]) -> bool:
    code = _failure_code(result)
    mode = result.mode.lower()
    return (mode, code) in allowed_failures or (ANY_MODE, code) in allowed_failures


def _unexpected_failures(
    results: list[AttemptResult],
    allowed_failures: set[tuple[str, str]],
) -> list[AttemptResult]:
    return [
        result
        for result in results
        if not result.ok and not _is_allowed_failure(result, allowed_failures)
    ]


def _assert_non_production(args: argparse.Namespace) -> None:
    target = args.target_env.strip().lower()
    base_url = args.base_url.strip().lower()
    looks_production = target in {"prod", "production"} or any(marker in base_url for marker in PRODUCTION_MARKERS)
    if looks_production and not args.allow_production:
        raise SystemExit(
            "Refusing to run against a production-looking target. Use a staging/dev "
            "backend, or pass --allow-production only after explicit approval."
        )
    if target not in {"local", "dev", "staging"} and not args.allow_production:
        raise SystemExit("--target-env must be one of local/dev/staging unless --allow-production is set.")
    if not args.i_understand_non_production and not args.allow_production:
        raise SystemExit("Pass --i-understand-non-production to confirm this is not a production run.")


def _run_health_check(base_url: str, timeout: float, label: str) -> bool:
    url = _backend_url(base_url, "/health")
    try:
        status, payload = _json_request(url, timeout)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[{label}] health check failed: {exc}")
        return False

    ok = 200 <= status < 300
    print(f"[{label}] health status={status} payload={json.dumps(payload, sort_keys=True)}")
    return ok


def _attempt_submission(
    *,
    index: int,
    mode: str,
    url: str,
    run_id: str,
    file_path: Path | None,
    timeout: float,
) -> AttemptResult:
    started = time.monotonic()
    try:
        status_code, payload = _post_multipart(
            url=url,
            fields=_synthetic_payload(index, run_id),
            file_path=file_path,
            timeout=timeout,
        )
    except (URLError, TimeoutError, OSError) as exc:
        return AttemptResult(
            index=index,
            mode=mode,
            ok=False,
            status_code=None,
            submission_id=None,
            code=type(exc).__name__,
            message=str(exc),
            elapsed_seconds=time.monotonic() - started,
        )

    detail = payload.get("detail", payload)
    if not isinstance(detail, dict):
        detail = {"message": str(detail)}

    submission_id = detail.get("submission_id") or payload.get("submission_id")
    ok = 200 <= status_code < 300 and bool(submission_id)
    return AttemptResult(
        index=index,
        mode=mode,
        ok=ok,
        status_code=status_code,
        submission_id=str(submission_id) if submission_id else None,
        code=str(detail.get("code", "")) or None,
        message=str(detail.get("message") or payload.get("message") or detail.get("body") or ""),
        elapsed_seconds=time.monotonic() - started,
    )


def _print_progress(result: AttemptResult) -> None:
    if result.ok:
        print(
            f"[submit {result.index:03d}] {result.mode}: ok "
            f"status={result.status_code} submission_id={result.submission_id} "
            f"elapsed={result.elapsed_seconds:.2f}s"
        )
        return

    print(
        f"[submit {result.index:03d}] {result.mode}: failed "
        f"status={result.status_code} code={result.code or '-'} "
        f"message={result.message or '-'} elapsed={result.elapsed_seconds:.2f}s"
    )


def _verify_results(
    *,
    before: SheetSnapshot | None,
    after: SheetSnapshot | None,
    results: list[AttemptResult],
    allowed_failures: set[tuple[str, str]],
) -> int:
    accepted_ids = [result.submission_id for result in results if result.ok and result.submission_id]
    unique_accepted_ids = set(accepted_ids)
    resume_attempts = [result for result in results if result.mode == "resume"]
    resume_successes = [result for result in resume_attempts if result.ok]
    quota_or_api = _quota_or_api_failures([result for result in results if not result.ok])
    unexpected_failures = _unexpected_failures(results, allowed_failures)
    exit_code = 0

    print("\nVerification")
    if unexpected_failures:
        print(f"- FAIL: {len(unexpected_failures)} unexpected synthetic submission failures occurred")
        for result in unexpected_failures[:10]:
            print(
                f"  submit {result.index:03d}: mode={result.mode} "
                f"status={result.status_code} code={_failure_code(result)} "
                f"message={result.message or '-'}"
            )
        exit_code = 1

    allowed_failed_results = [
        result for result in results if not result.ok and _is_allowed_failure(result, allowed_failures)
    ]
    if allowed_failed_results:
        print(f"- PASS: {len(allowed_failed_results)} failures matched explicit --allow-failure rules")

    if not accepted_ids:
        print("- FAIL: no submissions were accepted")
        exit_code = 1

    if resume_attempts and not resume_successes:
        print("- FAIL: no resume-upload submissions were accepted")
        exit_code = 1

    if quota_or_api:
        print(f"- FAIL: {len(quota_or_api)} quota/API-like failures occurred")
        exit_code = 1

    if len(accepted_ids) != len(unique_accepted_ids):
        print(f"- FAIL: duplicate accepted submission_id values detected ({len(accepted_ids)} accepted)")
        exit_code = 1
    else:
        print(f"- PASS: accepted submissions have unique submission_id values ({len(unique_accepted_ids)})")

    if before is None or after is None:
        print("- SKIP: sheet append verification was disabled")
        return exit_code

    before_submission_count = len(before.submissions)
    after_submission_count = len(after.submissions)
    appended_count = after_submission_count - before_submission_count
    after_submission_ids = _ids_from(after.submissions)
    missing_ids = sorted(unique_accepted_ids - after_submission_ids)

    if missing_ids:
        print(f"- FAIL: {len(missing_ids)} accepted IDs were not found in submissions sheet")
        print(f"  Missing IDs: {', '.join(missing_ids[:10])}")
        exit_code = 1
    else:
        print("- PASS: every accepted submission_id was found in the submissions sheet")

    if appended_count >= len(unique_accepted_ids):
        print(
            "- PASS: submissions sheet row count increased by "
            f"{appended_count} rows for {len(unique_accepted_ids)} accepted submissions"
        )
    else:
        print(
            "- FAIL: submissions sheet grew by "
            f"{appended_count} rows for {len(unique_accepted_ids)} accepted submissions"
        )
        exit_code = 1

    parser_ids = _ids_from(after.parser_results) - _ids_from(before.parser_results)
    error_ids = _ids_from(after.errors) - _ids_from(before.errors)
    covered_ids = unique_accepted_ids & (parser_ids | error_ids)
    accepted_resume_ids = {
        result.submission_id
        for result in results
        if result.ok and result.mode == "resume" and result.submission_id
    }
    missing_parser_or_error = sorted(accepted_resume_ids - covered_ids)
    print(
        "- INFO: post-run parser/error rows: "
        f"parser_results_new_ids={len(parser_ids)}, errors_new_ids={len(error_ids)}, "
        f"accepted_ids_with_parser_or_error={len(covered_ids)}"
    )
    if missing_parser_or_error:
        print(
            "- FAIL: "
            f"{len(missing_parser_or_error)} accepted resume submissions had no new parser_results or errors row"
        )
        print(f"  Missing IDs: {', '.join(missing_parser_or_error[:10])}")
        exit_code = 1
    elif accepted_resume_ids:
        print("- PASS: accepted resume submissions produced parser_results or errors rows")

    return exit_code


def _print_summary(
    results: list[AttemptResult],
    before: SheetSnapshot | None,
    after: SheetSnapshot | None,
    allowed_failures: set[tuple[str, str]],
) -> None:
    successes = [result for result in results if result.ok]
    failures = [result for result in results if not result.ok]
    allowed_failed_results = [result for result in failures if _is_allowed_failure(result, allowed_failures)]
    unexpected_failed_results = [result for result in failures if result not in allowed_failed_results]
    quota_or_api = _quota_or_api_failures(failures)
    by_mode: dict[str, dict[str, int]] = {}
    for result in results:
        stats = by_mode.setdefault(result.mode, {"attempted": 0, "successful": 0, "failed": 0})
        stats["attempted"] += 1
        stats["successful" if result.ok else "failed"] += 1

    print("\nSummary")
    print(f"- attempted: {len(results)}")
    print(f"- successful: {len(successes)}")
    print(f"- failed: {len(failures)}")
    print(f"- explicitly allowed failures: {len(allowed_failed_results)}")
    print(f"- unexpected failures: {len(unexpected_failed_results)}")
    print(f"- quota/API-like failures: {len(quota_or_api)}")
    for mode, stats in sorted(by_mode.items()):
        print(
            f"- {mode}: attempted={stats['attempted']} "
            f"successful={stats['successful']} failed={stats['failed']}"
        )

    if before is not None and after is not None:
        print(
            "- sheet rows: "
            f"submissions {len(before.submissions)} -> {len(after.submissions)}, "
            f"parser_results {len(before.parser_results)} -> {len(after.parser_results)}, "
            f"errors {len(before.errors)} -> {len(after.errors)}"
        )

    if quota_or_api:
        print("\nQuota/API-like failure samples")
        for result in quota_or_api[:10]:
            print(
                f"- submit {result.index:03d}: status={result.status_code} "
                f"code={result.code or '-'} message={result.message or '-'}"
            )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a synthetic 100-submission intake/load smoke test against staging/dev."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Intake endpoint path.")
    parser.add_argument("--target-env", required=True, help="One of local, dev, or staging.")
    parser.add_argument("--no-resume-count", type=int, default=50, help="Synthetic submissions without file upload.")
    parser.add_argument("--resume-count", type=int, default=50, help="Synthetic submissions with PDF upload.")
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR, help="Directory of synthetic PDFs.")
    parser.add_argument("--timeout-seconds", type=float, default=60.0, help="HTTP timeout per request.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Delay between submissions.")
    parser.add_argument("--parser-wait-seconds", type=float, default=20.0, help="Wait before final Sheet snapshot.")
    parser.add_argument("--env-file", type=Path, help="Optional env file for Sheet verification, such as backend/.env.")
    parser.add_argument(
        "--allow-failure",
        action="append",
        default=[],
        metavar="MODE:CODE",
        help=(
            "Explicitly allow an expected failed attempt. MODE is any, no_resume, "
            "or resume. CODE is the response error code, exception name, or "
            "HTTP_STATUS_### when no code is returned. Repeat as needed."
        ),
    )
    parser.add_argument("--skip-sheet-verify", action="store_true", help="Only verify API responses and health.")
    parser.add_argument("--i-understand-non-production", action="store_true", help="Confirm target is staging/dev/local.")
    parser.add_argument("--allow-production", action="store_true", help="Override production guard after approval.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    _assert_non_production(args)
    allowed_failures = _parse_allowed_failures(args.allow_failure)

    if args.no_resume_count < 0 or args.resume_count < 0:
        raise SystemExit("Submission counts must be non-negative.")
    total = args.no_resume_count + args.resume_count
    if total <= 0:
        raise SystemExit("At least one submission is required.")

    fixtures = _load_pdf_fixtures(args.fixture_dir)
    if args.resume_count and not fixtures:
        raise SystemExit(f"No PDF fixtures found under {args.fixture_dir}")

    run_id = uuid.uuid4().hex[:8]
    upload_url = _backend_url(args.base_url, args.endpoint)
    print(f"Libelle intake/load smoke run_id={run_id}")
    print(f"target_env={args.target_env} base_url={args.base_url} endpoint={args.endpoint}")
    print(
        f"attempts={total} no_resume={args.no_resume_count} resume={args.resume_count} "
        f"pdf_fixtures={len(fixtures)}"
    )

    if not _run_health_check(args.base_url, args.timeout_seconds, "pre-run"):
        return 1

    _load_env_file(args.env_file)
    before = None if args.skip_sheet_verify else _take_sheet_snapshot()

    results: list[AttemptResult] = []
    for offset in range(args.no_resume_count):
        index = offset + 1
        result = _attempt_submission(
            index=index,
            mode="no_resume",
            url=upload_url,
            run_id=run_id,
            file_path=None,
            timeout=args.timeout_seconds,
        )
        results.append(result)
        _print_progress(result)
        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)

    for offset in range(args.resume_count):
        index = args.no_resume_count + offset + 1
        file_path = fixtures[offset % len(fixtures)]
        result = _attempt_submission(
            index=index,
            mode="resume",
            url=upload_url,
            run_id=run_id,
            file_path=file_path,
            timeout=args.timeout_seconds,
        )
        results.append(result)
        _print_progress(result)
        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)

    if args.parser_wait_seconds > 0:
        print(f"\nWaiting {args.parser_wait_seconds:.1f}s for background parser/error rows...")
        time.sleep(args.parser_wait_seconds)

    after_health_ok = _run_health_check(args.base_url, args.timeout_seconds, "post-run")
    after = None if args.skip_sheet_verify else _take_sheet_snapshot()

    _print_summary(results, before, after, allowed_failures)
    verification_exit = _verify_results(
        before=before,
        after=after,
        results=results,
        allowed_failures=allowed_failures,
    )
    if not after_health_ok:
        verification_exit = 1
    return verification_exit


if __name__ == "__main__":
    raise SystemExit(main())
