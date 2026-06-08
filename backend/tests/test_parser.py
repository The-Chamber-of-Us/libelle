from parser import _is_section_header, _split_skill_line, extract_location


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