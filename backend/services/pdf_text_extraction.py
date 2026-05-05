"""
Shared PDF text extraction helper for Libelle.

Provides block-based PyMuPDF extraction with spatial sorting so that
extracted text follows visual reading order (top-to-bottom, left-to-right)
rather than internal PDF storage order.

Used by:
  - services/intake_service.py  (bytes path, from uploaded PDF)
  - scripts/benchmark.py        (file path, from local PDF files)
"""

from pathlib import Path

import fitz  # PyMuPDF


def _extract_text_from_fitz_doc(doc: fitz.Document) -> str:
    """
    Internal helper: extract and spatially sort text blocks from an open
    PyMuPDF document.

    Each page's text blocks are collected with their bounding box coordinates.
    Blocks are sorted top-to-bottom (y0), then left-to-right (x0) so the
    resulting string follows visual reading order rather than the internal
    PDF storage order fitz uses by default.

    Only text blocks (block type 0) are included — image blocks (type 1)
    are skipped.
    """
    blocks = []
    for page in doc:
        blocks.extend(page.get_text("blocks"))

    # sort by vertical position first, then horizontal
    blocks.sort(key=lambda b: (b[1], b[0]))

    # b[4] is the text content, b[6] is the block type (0 = text, 1 = image)
    return "\n".join(b[4] for b in blocks if b[6] == 0)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extract text from a PDF supplied as raw bytes.

    Used by intake_service.py when processing uploaded PDF files.
    Raises fitz.FileDataError if the bytes cannot be opened as a PDF.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return _extract_text_from_fitz_doc(doc)
    finally:
        doc.close()


def extract_text_from_pdf_path(pdf_path: Path) -> str:
    """
    Extract text from a PDF supplied as a file path.

    Used by scripts/benchmark.py when iterating over local PDF files.
    Raises fitz.FileNotFoundError if the path does not exist.
    """
    doc = fitz.open(str(pdf_path))
    try:
        return _extract_text_from_fitz_doc(doc)
    finally:
        doc.close()
