"""Canonical deterministic PDF-to-parser operation."""

from typing import Any, Dict

from parser import _parse_resume_with_skill_text
from services.pdf_text_extraction import ExtractedPdfText, extract_pdf_text_from_bytes
from services.skill_section_projection import project_skill_sections


def _parse_extracted_resume_pdf(extracted: ExtractedPdfText) -> Dict[str, Any]:
    """Parse a PDF extraction produced by the canonical extractor.

    This same-process seam is internal. Its result must be identical to parsing
    the source PDF bytes again with :func:`parse_resume_pdf`.
    """
    projection = project_skill_sections(extracted)
    return _parse_resume_with_skill_text(extracted.text, projection.text)


def parse_resume_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """Extract and parse one durable PDF in a single deterministic operation."""
    return _parse_extracted_resume_pdf(extract_pdf_text_from_bytes(pdf_bytes))
