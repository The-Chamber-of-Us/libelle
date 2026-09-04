from parser import (
    _is_section_header,
    _split_skill_line,
    extract_location,
    extract_project_experience,
    extract_skills,
    extract_work_experience,
)


def test_volunteering_is_section_header():
    """VOLUNTEERING should stop skill extraction."""
    assert _is_section_header("VOLUNTEERING") == True


def test_certifications_is_section_header():
    """CERTIFICATIONS should stop skill extraction."""
    assert _is_section_header("CERTIFICATIONS") == True


def test_additional_information_is_section_header():
    """ADDITIONAL INFORMATION should stop skill extraction."""
    assert _is_section_header("ADDITIONAL INFORMATION") == True


def test_sql_is_not_section_header():
    """Standalone uppercase tool SQL should not stop skill extraction."""
    assert _is_section_header("SQL") == False


def test_aws_is_not_section_header():
    """Standalone uppercase tool AWS should not stop skill extraction."""
    assert _is_section_header("AWS") == False


def test_gis_is_not_section_header():
    """Standalone uppercase tool GIS should not stop skill extraction."""
    assert _is_section_header("GIS") == False


def test_matlab_is_not_section_header():
    """Standalone uppercase tool MATLAB should not stop skill extraction."""
    assert _is_section_header("MATLAB") == False


def test_bullet_prefixed_skill_is_not_section_header():
    """Bullet-prefixed lines should never be treated as section headers."""
    assert _is_section_header("• SQL") == False
    assert _is_section_header("- Python") == False


def test_slash_list_splits_into_separate_skills():
    """Clear slash-delimited list should split into separate skills."""
    assert _split_skill_line("Python / Java / Go / Rust") == ["Python", "Java", "Go", "Rust"]


def test_slash_in_url_not_split():
    """Slashes in URLs should not be treated as delimiters."""
    result = _split_skill_line("https://github.com/user")
    assert len(result) == 1


def test_slash_in_version_string_not_split():
    """Version strings like Node.js 18/20 should not be split."""
    result = _split_skill_line("Node.js 18/20")
    assert len(result) == 1


def test_slash_with_long_parts_not_split():
    """Slash where parts are long compound phrases should not split."""
    result = _split_skill_line("Machine Learning / Deep Neural Network Architectures and Training")
    assert len(result) == 1


def test_no_slash_falls_back_to_standard_delimiters():
    """Lines without slash should still split on standard delimiters."""
    assert _split_skill_line("Python, Java, Go") == ["Python", " Java", " Go"]
    assert _split_skill_line("Python • Java • Go") == ["Python ", " Java ", " Go"]


def test_location_contact_line_email_and_location():
    text = "Maya Chen\nmaya.chen@example.com | Ithaca, NY"
    locs, conf = extract_location(text)
    assert "Ithaca, NY" in locs[0]
    assert conf == 1.0


def test_location_contact_line_email_phone_location():
    text = "Kevin Schmidt\nkevin@example.com | 555-123-4567 | Raleigh, NC"
    locs, conf = extract_location(text)
    assert "Raleigh, NC" in locs[0]
    assert conf == 1.0


def test_location_contact_line_url_and_location():
    text = "github.com/example | Austin, TX | example@email.com"
    locs, conf = extract_location(text)
    assert "Austin, TX" in locs[0]
    assert conf == 1.0


def test_location_no_false_positive_email_phone_url_only():
    text = "kevin@example.com | 555-123-4567 | https://github.com/example"
    locs, conf = extract_location(text)
    assert locs == []


def test_location_no_false_positive_email_only():
    text = "kevin@example.com"
    locs, conf = extract_location(text)
    assert locs == []


def test_location_no_false_positive_phone_only():
    text = "555-123-4567"
    locs, conf = extract_location(text)
    assert locs == []


def test_location_simple_standalone_still_works():
    text = "Jane Doe\nPortland, OR"
    locs, conf = extract_location(text)
    assert "Portland, OR" in locs[0]
    assert conf == 1.0


def test_extract_skills_from_tech_stack_header():
    text = "TECH STACK\nPython, React, PostgreSQL, Docker"
    skills, confidence = extract_skills(text)
    assert confidence == 1.0
    assert skills == ["python", "react", "postgresql", "docker"]


def test_extract_skills_from_technical_toolkit_header():
    text = (
        "TECHNICAL TOOLKIT:\n"
        "Languages: Python, JavaScript, SQL\n"
        "Platforms: AWS, Docker, GitHub Actions"
    )
    skills, confidence = extract_skills(text)
    assert confidence == 1.0
    assert skills == ["python", "javascript", "sql", "aws", "docker", "github actions"]


def test_extract_skills_from_core_technologies_header():
    text = "CORE   TECHNOLOGIES\nReact / Flask / PostgreSQL / Git"
    skills, confidence = extract_skills(text)
    assert confidence == 1.0
    assert skills == ["react", "flask", "postgresql", "git"]


def test_projects_is_not_treated_as_skills_section():
    text = "PROJECTS\nCourse Planner Web App\nBuilt a React and Flask prototype."
    skills, confidence = extract_skills(text)
    assert skills == []
    assert confidence == 0.0


def test_publications_is_not_treated_as_skills_section():
    text = "PUBLICATIONS\nChen M., Patel N. Data workflows in student support tools. In review."
    skills, confidence = extract_skills(text)
    assert skills == []
    assert confidence == 0.0


def test_leadership_is_not_treated_as_skills_section():
    text = (
        "LEADERSHIP\n"
        "Peer Tutor, Engineering Learning Initiatives\n"
        "Tutored students in introductory Python and data structures."
    )
    skills, confidence = extract_skills(text)
    assert skills == []
    assert confidence == 0.0


def test_resume_201_skills_stop_at_additional_projects():
    text = (
        "SKILLS\n"
        "Python, Java, SQL\n"
        "ADDITIONAL PROJECTS\n"
        "Student Organization Check-In Tracker\n"
        "Python and Airtable"
    )

    skills, confidence = extract_skills(text)

    assert confidence == 1.0
    assert skills == ["python", "java", "sql"]


def test_resume_203_skills_stop_at_additional_analytics_work():
    text = (
        "SKILLS\n"
        "SQL, Python, pandas, Tableau\n"
        "ADDITIONAL ANALYTICS WORK\n"
        "Referral Queue Aging Review\n"
        "Exported referral queue snapshots"
    )

    skills, confidence = extract_skills(text)

    assert confidence == 1.0
    assert skills == ["sql", "python", "pandas", "tableau"]


def test_resume_208_collects_every_explicit_skills_section():
    text = (
        "CORE COMPETENCIES\n"
        "Revenue operations, Salesforce reporting\n"
        "IMPACT HIGHLIGHTS\n"
        "Customer Expansion Analysis\n"
        "PROFESSIONAL BACKGROUND\n"
        "Revenue Operations Associate\n"
        "ACADEMIC TRAINING\n"
        "Bachelor of Arts in Economics\n"
        "TECHNICAL TOOLKIT\n"
        "Salesforce, Excel, SQL, Tableau\n"
        "SELECTED REPORTING WORK\n"
        "Renewal Forecast Hygiene"
    )

    skills, confidence = extract_skills(text)

    assert confidence == 1.0
    assert skills == [
        "revenue operations",
        "salesforce reporting",
        "salesforce",
        "excel",
        "sql",
        "tableau",
    ]


def test_subsequent_supported_skill_headings_are_not_extracted_as_skills():
    supported_headings = [
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
        "TOOLS AND TECHNOLOGIES",
        "AREAS OF EXPERTISE",
        "SKILLS & EXPERTISE",
        "SKILLS AND EXPERTISE",
        "TECHNICAL EXPERTISE",
        "PROGRAMMING LANGUAGES",
        "QUALIFICATIONS",
    ]
    text = "\n".join([*supported_headings, "Python", "EDUCATION", "BSc"])

    skills, confidence = extract_skills(text)

    assert confidence == 1.0
    assert skills == ["python"]


def test_collects_multiple_explicit_skill_sections_with_an_empty_section():
    text = (
        "SKILLS\n"
        "PROJECTS\n"
        "Portfolio\n"
        "TECHNICAL PROFICIENCIES\n"
        "Python, SQL\n"
        "EDUCATION\n"
        "BSc"
    )

    skills, confidence = extract_skills(text)

    assert confidence == 1.0
    assert skills == ["python", "sql"]


def test_adjacent_empty_skill_sections_are_safe():
    text = "SKILLS\nTECHNICAL SKILLS\nTOOLS\nEDUCATION\nBSc"

    skills, confidence = extract_skills(text)

    assert skills == []
    assert confidence == 0.0


def test_skill_specific_boundaries_do_not_stop_work_or_project_extraction():
    headings = [
        "ADDITIONAL PROJECTS",
        "ADDITIONAL ANALYTICS WORK",
        "IMPACT HIGHLIGHTS",
        "SELECTED REPORTING WORK",
    ]

    for heading in headings:
        work_text = f"WORK EXPERIENCE\nEngineer\n{heading}\nDetail\nEDUCATION\nBSc"
        work_entries, _, _ = extract_work_experience(work_text)
        assert work_entries == [f"Engineer {heading} Detail"]

        project_text = f"PROJECTS\nDashboard\n{heading}\nDetail\nEDUCATION\nBSc"
        project_entries, _ = extract_project_experience(project_text, 0)
        assert project_entries == [f"Dashboard {heading} Detail"]
