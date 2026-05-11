from parser import _is_section_header


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