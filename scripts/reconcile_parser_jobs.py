#!/usr/bin/env python3
"""Run one parser-job reconciliation sweep."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from services.parser_job_reconciliation import reconcile_missing_parser_jobs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create missing durable parser jobs for uploaded submissions."
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit non-zero when any eligible submission could not be recovered.",
    )
    args = parser.parse_args()

    summary = reconcile_missing_parser_jobs()
    print(
        "[PARSER_RECONCILE] summary "
        f"scanned={summary.scanned} eligible={summary.eligible} "
        f"recovered={summary.recovered} "
        f"skipped_existing_job={summary.skipped_existing_job} "
        f"skipped_successful_result={summary.skipped_successful_result} "
        f"skipped_not_uploaded={summary.skipped_not_uploaded} "
        f"failures={len(summary.failures)}"
    )

    if args.fail_on_error and summary.failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
