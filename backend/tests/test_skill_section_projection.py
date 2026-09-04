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


def test_full_width_skill_heading_fails_closed_and_remains_safe():
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

    assert projection.layout is LayoutKind.AMBIGUOUS
    assert skills == ["python", "sql", "docker", "aws"]


def _assert_fails_closed_without_unsupported_skills(
    extracted: ExtractedPdfText, unsupported: set[str]
):
    skills, projection = _skills(extracted)

    assert projection.layout is LayoutKind.AMBIGUOUS
    assert unsupported.isdisjoint(skills)
    return skills


def test_fragmented_single_column_contact_and_dates_fail_closed():
    extracted = _extracted(
        _block("CONTACT", 430, 30, width=120, index=0),
        _block("person@example.com", 430, 60, width=130, index=1),
        _block("PROFILE", 55, 35, width=170, index=2),
        _block("Operations specialist", 55, 70, width=260, index=3),
        _block("SKILLS", 55, 110, width=170, index=4),
        _block("Scheduling, Excel", 72, 140, width=230, index=5),
        _block("EXPERIENCE", 55, 200, width=170, index=6),
        _block("Coordinator", 72, 230, width=230, index=7),
        _block("2022 - 2024", 430, 235, width=120, index=8),
        _block("PROJECTS", 55, 390, width=170, index=9),
        _block("Managed office relocation", 72, 420, width=260, index=10),
        _block("2020 - 2022", 430, 425, width=120, index=11),
    )

    skills = _assert_fails_closed_without_unsupported_skills(
        extracted,
        {"2022 - 2024", "2020 - 2022", "coordinator", "managed office relocation"},
    )

    assert skills == ["scheduling", "excel"]


def test_hanging_indents_and_x_scatter_do_not_establish_lanes():
    extracted = _extracted(
        _block("CONTACT", 310, 30, width=180, index=0),
        _block("person@example.com", 315, 60, width=190, index=1),
        _block("SUMMARY", 60, 35, width=170, index=2),
        _block("Platform engineer", 64, 70, width=230, index=3),
        _block("SKILLS", 60, 115, width=170, index=4),
        _block("Python, SQL", 72, 145, width=210, index=5),
        _block("EXPERIENCE", 60, 210, width=170, index=6),
        _block("Senior Engineer", 85, 240, width=230, index=7),
        _block("2021 - Present", 320, 245, width=140, index=8),
        _block("PROJECTS", 60, 410, width=170, index=9),
        _block("Built billing workflows", 85, 440, width=240, index=10),
        _block("2020 - 2021", 315, 445, width=140, index=11),
    )

    skills = _assert_fails_closed_without_unsupported_skills(
        extracted,
        {
            "senior engineer",
            "2021 - present",
            "built billing workflows",
            "2020 - 2021",
        },
    )

    assert skills == ["python", "sql"]


def test_wide_mixed_skill_block_does_not_broadcast_skill_authority():
    extracted = _extracted(
        _block("SUMMARY", 55, 30, width=180, index=0),
        _block("Engineer", 55, 60, width=180, index=1),
        _block("CONTACT", 430, 30, width=130, index=2),
        _block("person@example.com", 430, 60, width=150, index=3),
        _block(
            "SKILLS\nPython, SQL, Docker, AWS, Kubernetes, Terraform, FastAPI",
            55,
            120,
            width=518,
            height=45,
            index=4,
        ),
        _block("EXPERIENCE", 55, 175, width=180, index=5),
        _block("Engineer", 55, 210, width=180, index=6),
        _block("2022 - 2024", 430, 210, width=130, index=7),
        _block("PROJECTS", 55, 380, width=180, index=8),
        _block("Built customer billing workflows", 55, 415, width=290, index=9),
        _block("EDUCATION", 430, 300, width=130, index=10),
        _block("BSc", 430, 335, width=130, index=11),
        _block("CERTIFICATIONS", 430, 460, width=145, index=12),
        _block("Cloud certificate", 430, 495, width=145, index=13),
    )

    skills = _assert_fails_closed_without_unsupported_skills(
        extracted,
        {"2022 - 2024", "built customer billing workflows", "engineer"},
    )

    assert skills == [
        "python",
        "sql",
        "docker",
        "aws",
        "kubernetes",
        "terraform",
        "fastapi",
    ]


def test_narrow_lane_skill_block_crossing_candidate_boundary_is_not_shared():
    extracted = _extracted(
        _block("SUMMARY", 36, 30, width=180, index=0),
        _block("Operations specialist", 36, 65, width=185, index=1),
        _block("CONTACT", 36, 180, width=90, index=2),
        _block("person@example.com", 36, 215, width=155, index=3),
        _block("EDUCATION\nSKILLS", 36, 350, width=145, height=80, index=4),
        _block("Python", 36, 450, width=100, index=5),
        _block("SQL", 36, 485, width=100, index=6),
        _block("Candidate Name", 220, 35, width=220, index=7),
        _block("EXPERIENCE", 258, 180, width=170, index=8),
        _block("Senior Engineer", 258, 215, width=230, index=9),
        _block("Built customer workflows", 258, 250, width=280, index=10),
        _block("PROJECTS", 258, 450, width=170, index=11),
        _block("Portfolio migration", 258, 485, width=240, index=12),
    )

    skills, projection = _skills(extracted)

    assert projection.layout is LayoutKind.MULTI_COLUMN
    assert skills == ["python", "sql"]


def test_left_gutter_headings_and_indented_single_flow_fail_closed():
    extracted = _extracted(
        _block("SUMMARY", 55, 30, width=90, index=0),
        _block("Platform engineer", 175, 35, width=300, index=1),
        _block("SKILLS", 55, 100, width=90, index=2),
        _block("Python, SQL", 175, 105, width=250, index=3),
        _block("EXPERIENCE", 55, 190, width=100, index=4),
        _block("Senior Engineer", 175, 195, width=250, index=5),
        _block("Led incident reviews", 175, 230, width=280, index=6),
        _block("PROJECTS", 55, 390, width=90, index=7),
        _block("Portfolio migration", 175, 395, width=270, index=8),
    )

    skills = _assert_fails_closed_without_unsupported_skills(
        extracted,
        {"senior engineer", "led incident reviews", "portfolio migration"},
    )

    assert skills == ["python", "sql"]


def test_full_width_section_transitions_do_not_emit_lane_narrative():
    extracted = _extracted(
        _block("SKILLS", 40, 35, width=532, index=0),
        _block("Python, SQL", 45, 80, width=205, index=1),
        _block("Docker, AWS", 335, 80, width=235, index=2),
        _block("EXPERIENCE", 40, 170, width=532, index=3),
        _block("Engineer", 45, 210, width=205, index=4),
        _block("Led platform migration", 335, 210, width=235, index=5),
        _block("PROJECTS", 40, 350, width=532, index=6),
        _block("Portfolio", 45, 390, width=205, index=7),
        _block("Built billing workflows", 335, 390, width=235, index=8),
    )

    skills = _assert_fails_closed_without_unsupported_skills(
        extracted,
        {"engineer", "led platform migration", "portfolio", "built billing workflows"},
    )

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


def _unsafe_shared_skill_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    blocks = (
        (fitz.Rect(55, 30, 250, 50), "SUMMARY"),
        (fitz.Rect(55, 60, 300, 80), "Platform engineer"),
        (fitz.Rect(430, 30, 575, 50), "CONTACT"),
        (fitz.Rect(430, 60, 575, 80), "person@example.com"),
        (
            fitz.Rect(55, 120, 575, 165),
            "SKILLS\nPython, SQL, Docker, AWS, Kubernetes, Terraform, "
            "FastAPI, PostgreSQL, Redis, GitHub Actions",
        ),
        (fitz.Rect(55, 175, 250, 195), "EXPERIENCE"),
        (fitz.Rect(55, 210, 300, 230), "Senior Engineer"),
        (fitz.Rect(430, 210, 575, 230), "2022 - 2024"),
        (fitz.Rect(430, 300, 575, 320), "EDUCATION"),
        (fitz.Rect(430, 335, 575, 355), "BSc"),
        (fitz.Rect(55, 380, 250, 400), "PROJECTS"),
        (fitz.Rect(55, 415, 350, 435), "Built customer billing workflows"),
        (fitz.Rect(430, 460, 575, 480), "CERTIFICATIONS"),
        (fitz.Rect(430, 495, 575, 515), "Cloud certificate"),
    )
    for rectangle, text in blocks:
        page.insert_textbox(rectangle, text, fontsize=10)
    value = document.tobytes()
    document.close()
    return value


def test_real_pdf_shared_skill_block_fails_closed_without_narrative():
    pdf_bytes = _unsafe_shared_skill_pdf_bytes()
    extracted = extract_pdf_text_from_bytes(pdf_bytes)

    skills, projection = _skills(extracted)
    canonical_skills = parse_resume_pdf(pdf_bytes)["skills"]["value"]

    assert projection.layout is LayoutKind.AMBIGUOUS
    assert skills == canonical_skills
    assert {
        "2022 - 2024",
        "senior engineer",
        "built customer billing workflows",
    }.isdisjoint(skills)
    assert {"python", "sql", "docker", "aws"}.issubset(skills)


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
