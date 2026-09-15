"""
Shared PDF text extraction helper for Libelle.

Provides block-based PyMuPDF extraction with spatial sorting so that
extracted text follows visual reading order (top-to-bottom, left-to-right)
rather than internal PDF storage order.

Used by:
  - services/intake_service.py  (bytes path, from uploaded PDF)
  - scripts/benchmark.py        (file path, from local PDF files)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import fitz  # PyMuPDF


class PasswordProtectedPDFError(ValueError):
    """Raised when an uploaded PDF requires a password to open."""


@dataclass(frozen=True)
class PositionedTextBlock:
    """A text block retained only for skill-section ownership decisions."""

    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass(frozen=True)
class PositionedTextPage:
    """Minimal page geometry needed to classify skill-section ownership."""

    width: float
    height: float
    blocks: Tuple[PositionedTextBlock, ...]


@dataclass(frozen=True)
class ExtractedPdfText:
    """Existing flattened text plus its internal positioned-text sidecar."""

    text: str
    positioned_pages: Tuple[PositionedTextPage, ...]


def _extract_pdf_text_from_fitz_doc(doc: fitz.Document) -> ExtractedPdfText:
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
    positioned_pages = []
    for page in doc:
        blocks = page.get_text("blocks")
        # filter to text blocks only, then sort within this page
        text_blocks = [block for block in blocks if block[6] == 0]
        text_blocks.sort(key=lambda block: (block[1], block[0]))
        pages_text.append("\n".join(block[4] for block in text_blocks))
        positioned_pages.append(
            PositionedTextPage(
                width=float(page.rect.width),
                height=float(page.rect.height),
                blocks=tuple(
                    PositionedTextBlock(
                        x0=float(block[0]),
                        y0=float(block[1]),
                        x1=float(block[2]),
                        y1=float(block[3]),
                        text=block[4],
                    )
                    for block in text_blocks
                ),
            )
        )
    return ExtractedPdfText(
        text="\n".join(pages_text),
        positioned_pages=tuple(positioned_pages),
    )


def _extract_text_from_fitz_doc(doc: fitz.Document) -> str:
    """Backward-compatible string-only wrapper for existing callers."""
    return _extract_pdf_text_from_fitz_doc(doc).text


def extract_pdf_text_from_bytes(pdf_bytes: bytes) -> ExtractedPdfText:
    """Extract flattened text and the internal skill-layout sidecar in one pass."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.needs_pass:
            raise PasswordProtectedPDFError("Password-protected PDFs are not supported")
        return _extract_pdf_text_from_fitz_doc(doc)
    finally:
        doc.close()


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extract text from a PDF supplied as raw bytes.

    Used by intake_service.py when processing uploaded PDF files.
    Raises fitz.FileDataError if the bytes cannot be opened as a PDF.
    """
    return extract_pdf_text_from_bytes(pdf_bytes).text


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
