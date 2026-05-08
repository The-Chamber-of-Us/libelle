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

    Each page's text blocks are sorted independently by (y0, x0) to preserve
    visual reading order within each page. Pages are then joined in document
    order. Sorting is done per-page rather than globally because PyMuPDF resets
    y0 to 0 at the top of every page — a global sort would cause blocks from
    different pages to be interleaved.

    Only text blocks (block type 0) are included — image blocks (type 1)
    are skipped.
    """
    pages_text = []
    for page in doc:
        blocks = page.get_text("blocks")
        # filter to text blocks only, then sort within this page
        text_blocks = [b for b in blocks if b[6] == 0]
        text_blocks.sort(key=lambda b: (b[1], b[0]))
        pages_text.append("\n".join(b[4] for b in text_blocks))
    return "\n".join(pages_text)


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
