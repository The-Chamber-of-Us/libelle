import json
import sys
from pathlib import Path

import fitz

GENERATOR_DIR = Path(__file__).parent.parent / "benchmarks" / "synthetic" / "generator"
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

from validate_generated import validate_generated  # noqa: E402


def _make_pdf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def _make_gold(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _v1_gold(case_id="syn_000_known", raw="Denver, CO"):
    return {
        "submission_id": case_id,
        "skills": ["python"],
        "location": {"city": "Denver", "country": "United States", "raw": raw},
        "notes": {"ambiguities": []},
    }


def test_valid_fixture_is_benchmark_ready(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    gold_dir = tmp_path / "golden_json"
    _make_pdf(pdf_dir / "syn_000_known.pdf", "Jordan Lee\nDenver, CO\nSkills: Python")
    _make_gold(gold_dir / "syn_000_known.json", _v1_gold())

    assert validate_generated(pdf_dir, gold_dir) is True


def test_malformed_annotation_is_not_ready(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    gold_dir = tmp_path / "golden_json"
    _make_pdf(pdf_dir / "syn_000_known.pdf", "Jordan Lee\nDenver, CO")
    gold_dir.mkdir(parents=True)
    (gold_dir / "syn_000_known.json").write_text("{not valid json", encoding="utf-8")

    assert validate_generated(pdf_dir, gold_dir) is False


def test_pdf_annotation_pairing_failure_is_not_ready(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    gold_dir = tmp_path / "golden_json"
    _make_pdf(pdf_dir / "syn_000_known.pdf", "Jordan Lee\nDenver, CO")
    gold_dir.mkdir(parents=True)
    # No matching gold.json written for syn_000_known.

    assert validate_generated(pdf_dir, gold_dir) is False


def test_fixture_identity_mismatch_is_not_ready(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    gold_dir = tmp_path / "golden_json"
    _make_pdf(pdf_dir / "syn_000_known.pdf", "Jordan Lee\nDenver, CO")
    _make_gold(gold_dir / "syn_000_known.json", _v1_gold(case_id="syn_999_other"))

    assert validate_generated(pdf_dir, gold_dir) is False


def test_unsupported_schema_version_is_not_ready(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    gold_dir = tmp_path / "golden_json"
    _make_pdf(pdf_dir / "syn_000_known.pdf", "Jordan Lee\nDenver, CO")
    # Neither V1 (submission_id + skills) nor V2 (resume_id/sections) shaped.
    _make_gold(gold_dir / "syn_000_known.json", {"some_field": "value"})

    assert validate_generated(pdf_dir, gold_dir) is False


def test_internal_consistency_failure_is_not_ready(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    gold_dir = tmp_path / "golden_json"
    # Rendered text does not contain the gold location.raw.
    _make_pdf(pdf_dir / "syn_000_known.pdf", "Jordan Lee\nNo location text here")
    _make_gold(gold_dir / "syn_000_known.json", _v1_gold(raw="Denver, CO"))

    assert validate_generated(pdf_dir, gold_dir) is False
