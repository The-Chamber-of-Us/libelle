import json
import sys
from pathlib import Path

import fitz
import pytest

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


def _v2_gold():
    return {
        "resume_id": "syn_000_known", "source_persona": "synthetic", "persona": "known",
        "name": "Jordan Lee", "email": None, "phone": None,
        "location": {"city": "Denver", "country": "United States", "raw": "Denver, CO"},
        "links": [], "skills": ["Python"], "notes": None,
        "sections": [{"heading": "SKILLS", "items": ["Python"]}],
    }


def test_valid_v2_fixture_is_ready(tmp_path, capsys):
    _make_pdf(tmp_path / "pdfs/syn_000_known.pdf", "Jordan Lee\nDenver, CO\nPython")
    _make_gold(tmp_path / "gold/syn_000_known.json", _v2_gold())
    assert validate_generated(tmp_path / "pdfs", tmp_path / "gold")
    assert "\nBENCHMARK-READY" in capsys.readouterr().out


@pytest.mark.parametrize("field,value,diagnostic", [
    ("sections", [{"heading": "EXPERIENCE", "items": [{"title": "Engineer"}]}],
     "missing required structured entry field"),
    ("sections", ["EXPERIENCE"], "expected section object"),
    ("sections", None, "expected array of section objects"),
    ("links", 42, "expected array"),
    ("location", "Denver", "expected object or null"),
    ("schema_version", "v3", "supported versions: v1, v2"),
    ("schema_version", None, "supported versions: v1, v2"),
    ("schema_version", "v1", "matching annotation shape"),
])
def test_invalid_v2_contract_reports_fixture_and_rule(tmp_path, capsys, field, value, diagnostic):
    gold = _v2_gold()
    gold[field] = value
    _make_pdf(tmp_path / "pdfs/syn_000_known.pdf", "Denver, CO")
    _make_gold(tmp_path / "gold/syn_000_known.json", gold)
    assert not validate_generated(tmp_path / "pdfs", tmp_path / "gold")
    output = capsys.readouterr().out
    assert "Fixture: syn_000_known" in output
    assert diagnostic in output
    assert "observed" in output
    assert "\nNOT BENCHMARK-READY" in output


def test_missing_v2_required_field_is_not_ready(tmp_path, capsys):
    gold = _v2_gold()
    del gold["phone"]
    _make_pdf(tmp_path / "pdfs/syn_000_known.pdf", "Denver, CO")
    _make_gold(tmp_path / "gold/syn_000_known.json", gold)
    assert not validate_generated(tmp_path / "pdfs", tmp_path / "gold")
    assert "phone: missing required top-level field" in capsys.readouterr().out


@pytest.mark.parametrize("gold", [[], None, {"location": {"raw": 42}}, {"location": ["Denver"]}])
def test_malformed_annotation_shape_does_not_crash(tmp_path, capsys, gold):
    _make_pdf(tmp_path / "pdfs/syn_000_known.pdf", "Denver, CO")
    _make_gold(tmp_path / "gold/syn_000_known.json", gold)
    assert not validate_generated(tmp_path / "pdfs", tmp_path / "gold")
    assert "Canonical benchmark corpus validation" in capsys.readouterr().out


def test_missing_pdf_is_not_ready(tmp_path, capsys):
    _make_gold(tmp_path / "gold/syn_000_known.json", _v2_gold())
    assert not validate_generated(tmp_path / "pdfs", tmp_path / "gold")
    assert "missing PDF" in capsys.readouterr().out


def test_unreadable_pdf_is_not_ready(tmp_path, capsys):
    pdf = tmp_path / "pdfs/syn_000_known.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(b"not a PDF")
    _make_gold(tmp_path / "gold/syn_000_known.json", _v2_gold())
    assert not validate_generated(tmp_path / "pdfs", tmp_path / "gold")
    assert "consistency check could not inspect" in capsys.readouterr().out


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_generation_validates_automatically_and_remains_deterministic(tmp_path, monkeypatch, capsys, version):
    import generate

    pdf_dir, gold_dir = tmp_path / "pdfs", tmp_path / "gold"
    monkeypatch.setattr(generate, "OUT_PDF", pdf_dir)
    monkeypatch.setattr(generate, "OUT_GOLD", gold_dir)
    monkeypatch.setattr(generate, "OUT_MANIFEST", tmp_path / "manifest.json")
    # Exercise real profile/annotation derivation without requiring WeasyPrint system libraries in CI.
    monkeypatch.setattr(generate, "_render_pdf", lambda env, css, template, profile, extras, path:
                        _make_pdf(path, profile.name + "\n" + profile.location.raw))
    args = ["--seed", "42", "--count", "2", "--annotation-version", version]
    assert generate.main(args) == 0
    first = {path.name: path.read_bytes() for path in gold_dir.glob("*.json")}
    assert generate.main(args) == 0
    assert first == {path.name: path.read_bytes() for path in gold_dir.glob("*.json")}
    assert "\nBENCHMARK-READY" in capsys.readouterr().out
    original = generate.derive_gold

    def invalid_annotation(profile, version):
        gold = original(profile, version=version)
        gold["schema_version"] = "v999"
        return gold

    monkeypatch.setattr(generate, "derive_gold", invalid_annotation)
    assert generate.main(args) == 1
    assert "\nNOT BENCHMARK-READY" in capsys.readouterr().out
