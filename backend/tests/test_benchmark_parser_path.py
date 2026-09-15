import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import benchmark

from services import resume_pdf_parser


def test_benchmark_uses_canonical_pdf_parser(monkeypatch, tmp_path):
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"durable benchmark pdf")
    captured = {}

    def fake_parse_resume_pdf(pdf_bytes):
        captured["pdf_bytes"] = pdf_bytes
        return {"skills": {"value": ["python"]}}

    monkeypatch.setattr(resume_pdf_parser, "parse_resume_pdf", fake_parse_resume_pdf)

    result, _ = benchmark._run_libelle(pdf_path)

    assert captured["pdf_bytes"] == b"durable benchmark pdf"
    assert result == {"skills": {"value": ["python"]}}
