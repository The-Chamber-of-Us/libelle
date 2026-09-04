from pathlib import Path

import fitz

from parser import SKILL_START_PATTERNS, parse_resume
from services.pdf_text_extraction import (
    ExtractedPdfText,
    PositionedTextBlock,
    PositionedTextPage,
    extract_pdf_text_from_bytes,
    extract_text_from_pdf_bytes,
    extract_text_from_pdf_path,
)
from services.resume_pdf_parser import _parse_extracted_resume_pdf, parse_resume_pdf
from services.skill_section_projection import LayoutKind, project_skill_sections


PAGE_WIDTH = 600.0
PAGE_HEIGHT = 800.0


def _block(
    text: str,
    x0: float,
    y0: float,
    *,
    page: int = 1,
    index: int = 0,
    width: float = 130.0,
    height: float = 20.0,
) -> tuple[int, int, PositionedTextBlock]:
    return (
        page,
        index,
        PositionedTextBlock(
            x0=x0,
            y0=y0,
            x1=x0 + width,
            y1=y0 + height,
            text=text,
        ),
    )


def _extracted(*items: tuple[int, int, PositionedTextBlock]) -> ExtractedPdfText:
    page_numbers = sorted({page for page, _, _ in items})
    pages = []
    flattened = []
    for page_number in page_numbers:
        blocks = [
            block
            for page, _, block in sorted(
                items,
                key=lambda item: (
                    item[0],
                    item[2].y0,
                    item[2].x0,
                    item[1],
                ),
            )
            if page == page_number
        ]
        pages.append(
            PositionedTextPage(
                width=PAGE_WIDTH,
                height=PAGE_HEIGHT,
                blocks=tuple(blocks),
            )
        )
        flattened.extend(block.text for block in blocks)
    return ExtractedPdfText(
        text="\n".join(flattened),
        positioned_pages=tuple(pages),
    )


def _skills(extracted: ExtractedPdfText):
    projection = project_skill_sections(extracted)
    parsed = _parse_extracted_resume_pdf(extracted)
    return parsed["skills"]["value"], projection


def test_single_column_collects_multiple_explicit_skill_sections():
    extracted = _extracted(
        _block("SKILLS", 60, 50, index=0),
        _block("Python, SQL", 60, 80, index=1),
        _block("PROJECTS", 60, 130, index=2),
        _block("Built APIs", 60, 160, index=3),
        _block("TOOLS", 60, 220, index=4),
        _block("Docker, AWS", 60, 250, index=5),
    )

    skills, projection = _skills(extracted)

    assert projection.layout is LayoutKind.SINGLE_COLUMN
    assert skills == ["python", "sql", "docker", "aws"]


def test_multi_column_scopes_skill_content_to_governing_lane():
    extracted = _extracted(
        _block("SKILLS", 45, 40, index=0),
        _block("Python, SQL", 45, 80, index=1),
        _block("PROJECTS", 45, 420, index=2),
        _block("Built APIs\nLed Teams", 45, 460, index=3, height=80),
        _block("EXPERIENCE", 350, 40, index=4),
        _block("Engineer", 350, 80, index=5),
        _block("WORK HISTORY", 350, 420, index=6),
        _block("Managed Python migration", 350, 460, index=7, height=80),
    )

    skills, projection = _skills(extracted)

    assert projection.layout is LayoutKind.MULTI_COLUMN
    assert skills == ["python", "sql"]
    assert "built apis" not in skills
    assert "managed python migration" not in skills


def test_ambiguous_layout_fails_closed_to_first_skill_section():
    extracted = _extracted(
        _block(
            "SKILLS\nPython\nPROJECTS\nBuilt APIs",
            45,
            40,
            index=0,
            height=500,
        ),
        _block(
            "TOOLS\nDocker\nEXPERIENCE\nLed Teams",
            350,
            40,
            index=1,
            height=500,
        ),
    )

    skills, projection = _skills(extracted)

    assert projection.layout is LayoutKind.AMBIGUOUS
    assert skills == ["python"]


def test_soft_skills_stops_section_but_later_supported_heading_is_collected():
    extracted = _extracted(
        _block("SKILLS", 60, 40, index=0),
        _block("Python", 60, 70, index=1),
        _block("SOFT SKILLS", 60, 100, index=2),
        _block("Leadership", 60, 130, index=3),
        _block("TOOLS", 60, 180, index=4),
        _block("Docker", 60, 210, index=5),
    )

    skills, _ = _skills(extracted)

    assert skills == ["python", "docker"]


def test_demonstrated_skill_local_boundaries_stop_narrative():
    for heading in (
        "ADDITIONAL PROJECTS",
        "ADDITIONAL ANALYTICS WORK",
        "IMPACT HIGHLIGHTS",
        "SELECTED REPORTING WORK",
    ):
        extracted = _extracted(
            _block("SKILLS", 60, 40, index=0),
            _block("Python", 60, 70, index=1),
            _block(heading, 60, 100, index=2),
            _block("Built customer reporting workflows", 60, 130, index=3),
            _block("TOOLS", 60, 180, index=4),
            _block("Docker", 60, 210, index=5),
        )

        skills, _ = _skills(extracted)

        assert skills == ["python", "docker"]


def test_empty_adjacent_skill_sections_are_safe():
    extracted = _extracted(
        _block("SKILLS", 60, 40, index=0),
        _block("TECHNICAL SKILLS", 60, 70, index=1),
        _block("TOOLS", 60, 100, index=2),
        _block("EDUCATION", 60, 130, index=3),
        _block("BSc", 60, 160, index=4),
    )

    skills, _ = _skills(extracted)

    assert skills == []


def test_every_supported_subsequent_skill_heading_is_skipped():
    # Use representative literal spellings for patterns containing alternatives.
    headings = [
        "SKILLS",
        "TECHNICAL SKILLS",
        "TOOLS",
        "TECH STACK",
        "TOOLKIT",
        "TECHNICAL TOOLKIT",
        "CORE TECHNOLOGIES",
        "CORE SKILLS",
        "KEY SKILLS",
        "PROFESSIONAL SKILLS",
        "TECHNICAL PROFICIENCIES",
        "CORE COMPETENCIES",
        "COMPETENCIES",
        "TECHNOLOGIES",
        "TOOLS & TECHNOLOGIES",
        "AREAS OF EXPERTISE",
        "SKILLS & EXPERTISE",
        "TECHNICAL EXPERTISE",
        "PROGRAMMING LANGUAGES",
        "QUALIFICATIONS",
    ]
    assert len(headings) == len(SKILL_START_PATTERNS)
    blocks = [
        _block(heading, 60, 30 + index * 25, index=index)
        for index, heading in enumerate(headings)
    ]
    blocks.append(_block("Python", 60, 30 + len(headings) * 25, index=len(headings)))

    skills, _ = _skills(_extracted(*blocks))

    assert skills == ["python"]


def test_multi_page_single_column_collects_later_tools_section():
    extracted = _extracted(
        _block("SKILLS\nPython\nPROJECTS\nPortfolio", 60, 40, page=1, index=0),
        _block("SUMMARY", 60, 300, page=1, index=1),
        _block("Engineer", 60, 330, page=1, index=2),
        _block("TOOLS\nDocker", 60, 40, page=2, index=0),
        _block("EDUCATION", 60, 300, page=2, index=1),
        _block("BSc", 60, 330, page=2, index=2),
    )

    skills, projection = _skills(extracted)

    assert projection.layout is LayoutKind.SINGLE_COLUMN
    assert skills == ["python", "docker"]


def test_ambiguous_page_makes_multi_page_document_fail_closed():
    extracted = _extracted(
        _block("SKILLS\nPython\nPROJECTS\nPortfolio", 60, 40, page=1, index=0),
        _block("SUMMARY", 60, 300, page=1, index=1),
        _block("Engineer", 60, 330, page=1, index=2),
        _block("TOOLS\nDocker\nEDUCATION\nBSc", 45, 40, page=2, index=0, height=500),
        _block("EXPERIENCE\nLed Teams", 350, 40, page=2, index=1, height=500),
    )

    skills, projection = _skills(extracted)

    assert projection.layout is LayoutKind.AMBIGUOUS
    assert skills == ["python"]


def test_heading_and_content_in_same_pdf_block_are_supported():
    extracted = _extracted(
        _block("SKILLS\nPython, SQL\nPROJECTS\nPortfolio", 60, 40, index=0),
        _block("TOOLS\nDocker", 60, 300, index=1),
        _block("EDUCATION\nBSc", 60, 500, index=2),
    )

    skills, _ = _skills(extracted)

    assert skills == ["python", "sql", "docker"]


def test_full_width_skill_heading_can_govern_two_safe_lanes():
    extracted = _extracted(
        _block("TECHNICAL SKILLS", 40, 35, width=532, index=0),
        _block("Python\nSQL", 45, 80, width=205, height=50, index=1),
        _block("EDUCATION", 45, 170, width=205, index=2),
        _block("BSc", 45, 200, width=205, index=3),
        _block("CERTIFICATIONS", 45, 340, width=205, index=4),
        _block("Example", 45, 370, width=205, index=5),
        _block("Docker\nAWS", 335, 80, width=235, height=50, index=6),
        _block("PROJECTS", 335, 170, width=235, index=7),
        _block("Migration\nBuilt APIs", 335, 200, width=235, height=50, index=8),
        _block("EXPERIENCE", 335, 350, width=235, index=9),
        _block("Engineer", 335, 380, width=235, index=10),
    )

    skills, projection = _skills(extracted)

    assert projection.layout is LayoutKind.MULTI_COLUMN
    assert skills == ["python", "sql", "docker", "aws"]


def test_isolated_right_aligned_contact_does_not_split_single_column_body():
    extracted = _extracted(
        _block("person@example.com", 430, 45, width=120, index=0),
        _block(
            "PROFILE\nEngineer\nSKILLS\nPython\nPROJECTS\nDemo\n"
            "Built APIs\nTOOLS\nDocker\nEDUCATION\nBSc",
            55,
            80,
            width=500,
            height=320,
            index=1,
        ),
    )

    skills, projection = _skills(extracted)

    assert projection.layout is LayoutKind.SINGLE_COLUMN
    assert skills == ["python", "docker"]


def test_projected_skills_do_not_change_non_skill_parser_fields():
    extracted = _extracted(
        _block("Jane Doe\nAustin, TX", 60, 30, index=0),
        _block("WORK EXPERIENCE\nEngineer\nBuilt reporting tools", 60, 90, index=1),
        _block("PROJECTS\nPortfolio", 60, 220, index=2),
        _block("EDUCATION\nBSc", 60, 300, index=3),
        _block("SKILLS\nPython", 60, 380, index=4),
        _block("TOOLS\nSQL", 60, 450, index=5),
    )
    baseline = parse_resume(extracted.text)
    projected = _parse_extracted_resume_pdf(extracted)

    assert projected["skills"]["value"] == ["python", "sql"]
    assert {
        key: value for key, value in projected.items() if key != "skills"
    } == {
        key: value for key, value in baseline.items() if key != "skills"
    }


def _sample_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(
        fitz.Rect(72, 72, 540, 400),
        "SKILLS\nPython\nPROJECTS\nBuilt APIs\nTOOLS\nDocker\nEDUCATION\nBSc",
    )
    value = document.tobytes()
    document.close()
    return value


def test_existing_bytes_extraction_caller_returns_identical_flattened_text():
    pdf_bytes = _sample_pdf_bytes()

    rich = extract_pdf_text_from_bytes(pdf_bytes)

    assert extract_text_from_pdf_bytes(pdf_bytes) == rich.text
    assert rich.positioned_pages


def test_existing_path_extraction_caller_returns_identical_flattened_text(tmp_path):
    pdf_path = Path(tmp_path) / "resume.pdf"
    pdf_path.write_bytes(_sample_pdf_bytes())

    assert extract_text_from_pdf_path(pdf_path) == extract_pdf_text_from_bytes(
        pdf_path.read_bytes()
    ).text


def test_canonical_pdf_parse_replays_identically_after_restart():
    pdf_bytes = _sample_pdf_bytes()

    intake_extraction = extract_pdf_text_from_bytes(pdf_bytes)
    same_process_result = _parse_extracted_resume_pdf(intake_extraction)

    del intake_extraction
    restarted_worker_result = parse_resume_pdf(pdf_bytes)

    assert restarted_worker_result == same_process_result
    assert restarted_worker_result["skills"]["value"] == ["python", "docker"]
