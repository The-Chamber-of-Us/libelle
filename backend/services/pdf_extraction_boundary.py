"""Killable PDF extraction; no parser code executes in the calling process."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import BoundedSemaphore

from config import (
    MAX_PDF_MB, MAX_PDF_PAGES, MAX_PDF_TEXT_BYTES,
    PDF_EXTRACTION_TIMEOUT_SECONDS, PDF_EXTRACTION_MEMORY_MB,
    PDF_EXTRACTION_MAX_CONCURRENT,
)
from services.pdf_text_extraction import (
    ExtractedPdfText, PositionedTextPage, PositionedTextBlock,
    PasswordProtectedPDFError, PDFResourceLimitError,
)
import fitz

_slots = BoundedSemaphore(PDF_EXTRACTION_MAX_CONCURRENT)
_WORKER = Path(__file__).with_name('pdf_extraction_worker.py')


def extract_bounded(pdf_bytes: bytes) -> ExtractedPdfText:
    if len(pdf_bytes) > MAX_PDF_MB * 1024 * 1024:
        raise PDFResourceLimitError('FILE_TOO_LARGE')
    if not _slots.acquire(blocking=False):
        raise PDFResourceLimitError('PDF_EXTRACTION_BUSY')
    try:
        with tempfile.TemporaryDirectory(prefix='libelle-pdf-') as directory:
            source = Path(directory) / 'input.pdf'
            output = Path(directory) / 'output.json'
            source.write_bytes(pdf_bytes)
            # Geometry/JSON overhead is bounded independently of extracted text.
            output_limit = MAX_PDF_TEXT_BYTES * 32 + MAX_PDF_PAGES * 1024
            command = [sys.executable, str(_WORKER), str(source), str(output),
                       str(MAX_PDF_PAGES), str(MAX_PDF_TEXT_BYTES),
                       str(PDF_EXTRACTION_MEMORY_MB), str(output_limit)]
            try:
                # run() kills AND reaps the child on timeout. No pipe can accumulate
                # unbounded native-library diagnostics in the parent process.
                result = subprocess.run(command, timeout=PDF_EXTRACTION_TIMEOUT_SECONDS,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.TimeoutExpired as exc:
                raise PDFResourceLimitError('PDF_EXTRACTION_TIMEOUT') from exc
            if result.returncode != 0 or not output.exists():
                raise PDFResourceLimitError('PDF_PROCESSING_LIMIT')
            with output.open('rb') as stream:
                payload = stream.read(output_limit + 1)
            if len(payload) > output_limit:
                raise PDFResourceLimitError('PDF_TEXT_TOO_LARGE')
            data = json.loads(payload)
            if data.get('error') == 'PASSWORD_PROTECTED_PDF':
                raise PasswordProtectedPDFError('Password-protected PDF')
            if data.get('error') == 'INVALID_PDF':
                raise fitz.FileDataError('Unreadable PDF')
            if data.get('error'):
                raise PDFResourceLimitError(data['error'])
            return ExtractedPdfText(data['text'], tuple(
                PositionedTextPage(page['width'], page['height'], tuple(
                    PositionedTextBlock(**block) for block in page['blocks']
                )) for page in data['positioned_pages']
            ))
    finally:
        _slots.release()
