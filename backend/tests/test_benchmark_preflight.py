import json
from pathlib import Path

import pytest

from benchmarks.preflight import format_preflight_report, run_preflight


def _write_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n")


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _v1_golden(submission_id="resume_01"):
    return {
        "submission_id": submission_id,
        "skills": ["python"],
        "location": {"city": "Denver", "country": "United States", "raw": "Denver, CO"},
    }


def test_matched_corpus_is_valid(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "resume_01.pdf")
    _write_json(golden_dir / "resume_01.json", _v1_golden("resume_01"))

    result = run_preflight(pdf_dir, golden_dir)

    assert result.ok
    assert result.pdf_count == 1
    assert result.golden_count == 1
    assert result.matched_count == 1
    assert result.errors == []


def test_empty_corpus_is_invalid(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    pdf_dir.mkdir()
    golden_dir.mkdir()

    result = run_preflight(pdf_dir, golden_dir)

    assert not result.ok
    assert "empty benchmark corpus" in result.errors[0].message


def test_missing_golden_fails_by_default(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "resume_01.pdf")
    golden_dir.mkdir()

    result = run_preflight(pdf_dir, golden_dir)

    assert not result.ok
    assert any("missing golden JSON" in i.message for i in result.errors)


def test_missing_golden_is_warning_with_allow_missing(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "resume_01.pdf")
    golden_dir.mkdir()

    result = run_preflight(pdf_dir, golden_dir, allow_missing=True)

    assert result.ok
    assert any("missing golden JSON" in w.message for w in result.warnings)


def test_missing_pdf_fails_by_default(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    pdf_dir.mkdir()
    _write_json(golden_dir / "resume_01.json", _v1_golden("resume_01"))

    result = run_preflight(pdf_dir, golden_dir)

    assert not result.ok
    assert any("missing PDF" in i.message for i in result.errors)


def test_duplicate_fixture_ids_fail(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "resume_01.pdf")
    _write_pdf(pdf_dir / "resume_02.pdf")
    # Both files declare the same internal submission_id.
    _write_json(golden_dir / "resume_01.json", _v1_golden("resume_01"))
    _write_json(golden_dir / "resume_02.json", _v1_golden("resume_01"))

    result = run_preflight(pdf_dir, golden_dir)

    assert not result.ok
    assert any("duplicate fixture ID" in i.message for i in result.errors)


def test_mismatched_internal_id_fails(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "multi_col_04.pdf")
    _write_json(golden_dir / "multi_col_04.json", _v1_golden("multi_col_05"))

    result = run_preflight(pdf_dir, golden_dir)

    assert not result.ok
    issue = next(i for i in result.errors if i.fixture_id == "multi_col_04")
    assert issue.expected == "multi_col_04"
    assert issue.found == "multi_col_05"
    assert "Expected ID: multi_col_04" in issue.format()
    assert "Found ID: multi_col_05" in issue.format()


def test_malformed_json_fails(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "resume_01.pdf")
    golden_dir.mkdir()
    (golden_dir / "resume_01.json").write_text("{not valid json", encoding="utf-8")

    result = run_preflight(pdf_dir, golden_dir)

    assert not result.ok
    assert any("malformed JSON" in i.message for i in result.errors)


def test_missing_required_v1_fields_fail(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "resume_01.pdf")
    _write_json(golden_dir / "resume_01.json", {"submission_id": "resume_01", "skills": ["python"]})

    result = run_preflight(pdf_dir, golden_dir)

    assert not result.ok
    assert any("missing required 'location' object" in i.message for i in result.errors)


def test_mixed_schema_versions_warn_not_fail(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "resume_01.pdf")
    _write_json(golden_dir / "resume_01.json", _v1_golden("resume_01"))
    _write_pdf(pdf_dir / "resume_201.pdf")
    _write_json(
        golden_dir / "resume_201.json",
        {"resume_id": "resume_201", "skills": ["python"], "sections": []},
    )

    result = run_preflight(pdf_dir, golden_dir)

    assert result.ok
    assert any("mixed schema versions" in w.message for w in result.warnings)


def test_format_report_success(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "resume_01.pdf")
    _write_json(golden_dir / "resume_01.json", _v1_golden("resume_01"))

    result = run_preflight(pdf_dir, golden_dir)
    report = format_preflight_report(result)

    assert "Benchmark preflight" in report
    assert "✓ 1 PDFs found" in report
    assert "Starting benchmark..." in report


def test_format_report_failure(tmp_path):
    pdf_dir = tmp_path / "resumes"
    golden_dir = tmp_path / "golden_json"
    _write_pdf(pdf_dir / "multi_col_04.pdf")
    _write_json(golden_dir / "multi_col_04.json", _v1_golden("multi_col_05"))

    result = run_preflight(pdf_dir, golden_dir)
    report = format_preflight_report(result)

    assert "Benchmark aborted" in report
    assert "Fixture: multi_col_04" in report
    assert "Expected ID: multi_col_04" in report
    assert "Found ID: multi_col_05" in report
