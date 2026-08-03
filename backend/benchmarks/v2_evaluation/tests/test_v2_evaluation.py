import json
from pathlib import Path

from backend.benchmarks.v2_evaluation.score_v2_structure import (
    evaluate,
    score_current_parser_fields,
)
from backend.benchmarks.v2_evaluation.validate_v2_goldens import discover_and_validate


def _write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(json.dumps(data), encoding="utf-8")


def _golden(resume_id="resume_001"):
    return {
        "resume_id": resume_id,
        "source_persona": "slice",
        "persona": "persona",
        "name": "A Candidate",
        "email": None,
        "phone": None,
        "location": {"city": "", "country": "", "raw": "Remote"},
        "links": [],
        "skills": ["Python"],
        "notes": None,
        "sections": [
            {
                "heading": "EXPERIENCE",
                "items": [
                    {
                        "title": "Developer",
                        "meta": "2025",
                        "subtitle": "Remote",
                        "bullets": ["Built tools."],
                    }
                ],
            },
            {"heading": "SKILLS", "items": ["Python"]},
            {
                "heading": "CERTIFICATIONS",
                "items": [
                    "AWS Certified Cloud Practitioner, 2025",
                    {
                        "title": "Data Award",
                        "meta": "2024",
                        "subtitle": "City Lab",
                        "bullets": [],
                    },
                ],
            },
        ],
    }


def test_valid_v2_fixture(tmp_path):
    _write(tmp_path / "pdf" / "resume_001.pdf", b"%PDF")
    _write(tmp_path / "gold" / "resume_001.json", _golden())

    records = discover_and_validate(tmp_path / "pdf", tmp_path / "gold")

    assert len(records) == 1
    assert records[0].valid
    assert records[0].schema_version == "v2"


def test_malformed_root_schema(tmp_path):
    bad = _golden()
    bad.pop("sections")
    _write(tmp_path / "pdf" / "resume_001.pdf", b"%PDF")
    _write(tmp_path / "gold" / "resume_001.json", bad)

    records = discover_and_validate(tmp_path / "pdf", tmp_path / "gold")

    assert records[0].schema_version == "v2"
    assert not records[0].valid
    assert any("missing required top-level field" in issue.message for issue in records[0].issues)


def test_malformed_sections_shape(tmp_path):
    bad = _golden()
    bad["sections"] = [{"heading": "EXPERIENCE", "items": [{"title": ""}]}]
    _write(tmp_path / "pdf" / "resume_001.pdf", b"%PDF")
    _write(tmp_path / "gold" / "resume_001.json", bad)

    records = discover_and_validate(tmp_path / "pdf", tmp_path / "gold")

    messages = [issue.message for issue in records[0].issues]
    assert "expected non-empty string" in messages
    assert any("missing required structured entry field" == msg for msg in messages)


def test_mismatched_filename_and_resume_id(tmp_path):
    _write(tmp_path / "pdf" / "resume_999.pdf", b"%PDF")
    _write(tmp_path / "gold" / "resume_999.json", _golden("resume_001"))

    records = discover_and_validate(tmp_path / "pdf", tmp_path / "gold")

    assert any("does not match filename stem" in issue.message for issue in records[0].issues)


def test_missing_pdf_or_json_pair(tmp_path):
    _write(tmp_path / "pdf" / "only_pdf.pdf", b"%PDF")
    _write(tmp_path / "gold" / "only_json.json", _golden("only_json"))

    records = discover_and_validate(tmp_path / "pdf", tmp_path / "gold")

    all_messages = [issue.message for record in records for issue in record.issues]
    assert any("missing JSON pair" in msg for msg in all_messages)
    assert any("missing PDF pair" in msg for msg in all_messages)


def test_duplicate_ids(tmp_path):
    _write(tmp_path / "pdf" / "a.pdf", b"%PDF")
    _write(tmp_path / "pdf" / "b.pdf", b"%PDF")
    _write(tmp_path / "gold" / "a.json", _golden("a"))
    _write(tmp_path / "gold" / "b.json", _golden("a"))

    records = discover_and_validate(tmp_path / "pdf", tmp_path / "gold")

    assert any(
        "duplicate ID" in issue.message
        for record in records
        for issue in record.issues
    )


def test_mixed_string_and_structured_items_valid(tmp_path):
    _write(tmp_path / "pdf" / "resume_001.pdf", b"%PDF")
    _write(tmp_path / "gold" / "resume_001.json", _golden())

    records = discover_and_validate(tmp_path / "pdf", tmp_path / "gold")

    assert records[0].valid


def test_unsupported_fields_without_prediction(tmp_path):
    _write(tmp_path / "pdf" / "resume_001.pdf", b"%PDF")
    _write(tmp_path / "gold" / "resume_001.json", _golden())

    summary = evaluate(pdf_dir=tmp_path / "pdf", golden_dir=tmp_path / "gold")

    fixture = summary["fixtures"][0]
    assert fixture["evaluated_metric_names"] == []
    assert "skills" not in fixture["unsupported_fields"]
    assert "sections" in fixture["unsupported_fields"]
    assert "title_matching" in fixture["unsupported_fields"]


def test_empty_evaluation_input(tmp_path):
    (tmp_path / "pdf").mkdir()
    (tmp_path / "gold").mkdir()

    records = discover_and_validate(tmp_path / "pdf", tmp_path / "gold")

    assert not records[0].valid
    assert "no PDF or JSON fixtures found" in records[0].issues[0].message


def test_explicit_root_and_v2_corpus_paths(tmp_path):
    _write(tmp_path / "pdf" / "root.pdf", b"%PDF")
    _write(tmp_path / "gold" / "root.json", _golden("root"))
    _write(tmp_path / "pdf" / "v2" / "resume_201.pdf", b"%PDF")
    _write(tmp_path / "gold" / "v2" / "resume_201.json", _golden("resume_201"))

    root_records = discover_and_validate(tmp_path / "pdf", tmp_path / "gold")
    v2_records = discover_and_validate(tmp_path / "pdf" / "v2", tmp_path / "gold" / "v2")

    assert len(root_records) == 2
    assert len(v2_records) == 1
    assert all(record.valid for record in root_records + v2_records)


def test_validation_failure_blocks_evaluation(tmp_path):
    bad = _golden()
    bad["sections"] = [{"heading": "EXPERIENCE", "items": [{"title": ""}]}]
    _write(tmp_path / "pdf" / "resume_001.pdf", b"%PDF")
    _write(tmp_path / "gold" / "resume_001.json", bad)

    summary = evaluate(pdf_dir=tmp_path / "pdf", golden_dir=tmp_path / "gold")

    fixture = summary["fixtures"][0]
    assert fixture["validation_status"] == "invalid"
    assert fixture["eligible_for_evaluation"] is False
    assert fixture["evaluated_metric_names"] == []
    assert fixture["metric_values"] == {}


def test_scores_current_parser_supported_fields():
    golden = _golden()
    golden["phone"] = "(555) 010-2222"
    predicted = {
        "skills": {"value": ["python", "SQL"]},
        "locations": {"value": ["Remote"]},
        "phones": {"value": ["5550102222"]},
    }

    metrics = score_current_parser_fields(golden, predicted)

    assert metrics["skills"]["tp"] == 1
    assert metrics["skills"]["fp"] == 1
    assert metrics["location"]["components"]["raw"]["status"] == "match"
    assert metrics["phone"]["tp"] == 1
