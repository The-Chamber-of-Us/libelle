"""Observable ownership regressions through durable PDF bytes, without mocks."""

from collections import Counter
import sys
from pathlib import Path

import pytest

from benchmarks.layout_regression.generate import generate, load_cases, render_pdf
from benchmarks.synthetic.generator.validate_generated import validate_generated
from services.pdf_text_extraction import extract_pdf_text_from_bytes
from services.resume_pdf_parser import parse_resume_pdf
from services.skill_section_projection import project_skill_sections


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
import benchmark


CASES = load_cases()


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("layout-corpus"))


def test_generated_corpus_passes_existing_validation(corpus):
    assert validate_generated(*corpus)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_layout_skill_ownership(case, corpus):
    pdf = corpus[0] / f'{case["id"]}.pdf'
    data = pdf.read_bytes()
    assert data == render_pdf(case)

    extracted = extract_pdf_text_from_bytes(data)
    # Check every annotated line survives rendering: a clipped safety sentinel
    # must never turn an ownership test into a vacuous pass.
    for block in case["blocks"]:
        for line in block["text"].splitlines():
            assert line in extracted.text

    parsed = parse_resume_pdf(data)
    skills = parsed["skills"]["value"]
    assert skills == case["expected_skills"]
    assert len(skills) == len(set(skills))
    for excluded in case["excluded"]:
        assert all(excluded not in skill for skill in skills)

    benchmark_result, _ = benchmark._run_libelle(pdf)
    assert benchmark_result == parsed

    # Secondary geometry checks ensure renderer changes don't silently remove
    # the failure condition. Final emitted skills above remain the oracle.
    projection = project_skill_sections(extracted)
    assert projection.layout.name == case["layout"]
    # Parser token deduplication can hide shared-block duplication, so also
    # check that projection never repeats an owned line in these unique inputs.
    counts = Counter(projection.text.splitlines()[1:])
    assert all(count == 1 for count in counts.values())
    if case["crossing_text"]:
        block, = [
            block for block in extracted.positioned_pages[0].blocks
            if case["crossing_text"] in block.text
        ]
        assert block.x0 < case["candidate_boundary"] < block.x1
        if case["id"] == "wide_skill_start":
            assert block.x1 - block.x0 >= 640 * 0.70
        else:
            assert block.x1 - block.x0 < 640 * 0.70
