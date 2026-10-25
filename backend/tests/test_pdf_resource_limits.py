"""Exercise real child processes and the public rejection/persistence contract."""
import os
from pathlib import Path
from threading import BoundedSemaphore
import time

import fitz
import pytest

from services import pdf_extraction_boundary as boundary
from services.intake_file_validation import validate_resume_upload, ResumeFileValidationError
from services.pdf_text_extraction import extract_text_from_pdf_bytes, PDFResourceLimitError
from tests.test_intake_route_rate_limit import _client, _upload
from api.routes import intake
from services import intake_service
from services.rate_limit import InMemoryIntakeRateLimiter


def pdf(pages=1, text='resume'):
    with fitz.open() as doc:
        for _ in range(pages):
            doc.new_page().insert_text((72, 72), text)
        return doc.tobytes()


def test_normal_pdf_and_exact_text_boundary(monkeypatch):
    monkeypatch.setattr(boundary, 'MAX_PDF_TEXT_BYTES', 7)
    assert extract_text_from_pdf_bytes(pdf()) == 'resume\n'
    monkeypatch.setattr(boundary, 'MAX_PDF_TEXT_BYTES', 6)
    with pytest.raises(PDFResourceLimitError, match='PDF_TEXT_TOO_LARGE'):
        extract_text_from_pdf_bytes(pdf())


def test_page_count_boundary(monkeypatch):
    monkeypatch.setattr(boundary, 'MAX_PDF_PAGES', 2)
    assert extract_text_from_pdf_bytes(pdf(2)) == 'resume\n\nresume\n'
    with pytest.raises(PDFResourceLimitError, match='PDF_TOO_MANY_PAGES'):
        extract_text_from_pdf_bytes(pdf(3))


def test_malformed_pdf():
    with pytest.raises(ResumeFileValidationError) as caught:
        validate_resume_upload(filename='a.pdf', content_type='application/pdf', file_bytes=b'%PDF-broken')
    assert caught.value.code == 'INVALID_PDF'


def test_timeout_kills_and_reaps_child_and_releases_slot(monkeypatch, tmp_path):
    worker = tmp_path / 'hang.py'
    pid_file = tmp_path / 'pid'
    worker.write_text(f'import os, time\nfrom pathlib import Path\nPath({str(pid_file)!r}).write_text(str(os.getpid()))\ntime.sleep(60)\n')
    real_worker = boundary._WORKER
    monkeypatch.setattr(boundary, '_WORKER', worker)
    monkeypatch.setattr(boundary, '_slots', BoundedSemaphore(1))
    monkeypatch.setattr(boundary, 'PDF_EXTRACTION_TIMEOUT_SECONDS', 1)
    start = time.monotonic()
    with pytest.raises(PDFResourceLimitError, match='PDF_EXTRACTION_TIMEOUT'):
        extract_text_from_pdf_bytes(pdf())
    assert time.monotonic() - start < 5
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)
    monkeypatch.setattr(boundary, '_WORKER', real_worker)
    assert extract_text_from_pdf_bytes(pdf()) == 'resume\n'


def test_saturation_fails_without_spawning(monkeypatch):
    slots = BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(boundary, '_slots', slots)
    monkeypatch.setattr(boundary.subprocess, 'run', lambda *a, **k: pytest.fail('must not spawn'))
    with pytest.raises(PDFResourceLimitError, match='PDF_EXTRACTION_BUSY'):
        extract_text_from_pdf_bytes(pdf())


def test_crashed_worker_is_controlled(monkeypatch, tmp_path):
    worker = tmp_path / 'crash.py'
    worker.write_text('import os\nos._exit(9)\n')
    monkeypatch.setattr(boundary, '_WORKER', worker)
    with pytest.raises(PDFResourceLimitError, match='PDF_PROCESSING_LIMIT'):
        extract_text_from_pdf_bytes(pdf())


@pytest.mark.parametrize('code', ['PDF_TOO_MANY_PAGES', 'PDF_TEXT_TOO_LARGE',
                                  'PDF_EXTRACTION_TIMEOUT', 'PDF_PROCESSING_LIMIT',
                                  'PDF_EXTRACTION_BUSY'])
def test_route_error_contract_and_no_side_effects(monkeypatch, code):
    def reject(_):
        raise PDFResourceLimitError(code)
    monkeypatch.setattr(boundary, 'extract_bounded', reject)
    for name in ('upload_pdf', 'write_base_row', 'create_parser_job'):
        monkeypatch.setattr(intake_service, name, lambda *a, **k: pytest.fail('rejection must not persist'))
    monkeypatch.setattr(intake, 'intake_rate_limiter', InMemoryIntakeRateLimiter(
        enabled=False, per_ip_limit=0, per_email_limit=0, global_limit=0))
    response = _upload(_client())
    assert response.status_code == (503 if code == 'PDF_EXTRACTION_BUSY' else 400)
    assert response.json()['detail']['status'] == 'error'
    assert response.json()['detail']['code'] == code


def test_oversized_upload_keeps_413_contract(monkeypatch):
    from services import intake_file_validation
    monkeypatch.setattr(intake_file_validation, 'MAX_PDF_MB', 1)
    monkeypatch.setattr(boundary.subprocess, 'run', lambda *a, **k: pytest.fail('must not extract'))
    with pytest.raises(ResumeFileValidationError) as caught:
        validate_resume_upload(filename='resume.pdf', content_type='application/pdf',
                               file_bytes=b'%PDF-' + b'x' * 1024**2)
    assert caught.value.status_code == 413
    assert caught.value.code == 'FILE_TOO_LARGE'


def test_oversized_worker_output_is_controlled(monkeypatch, tmp_path):
    worker = tmp_path / 'large_output.py'
    worker.write_text('import sys\nfrom pathlib import Path\nPath(sys.argv[2]).write_bytes(b"x" * (int(sys.argv[7]) + 1))\n')
    monkeypatch.setattr(boundary, '_WORKER', worker)
    monkeypatch.setattr(boundary, 'MAX_PDF_TEXT_BYTES', 10)
    monkeypatch.setattr(boundary, 'MAX_PDF_PAGES', 1)
    with pytest.raises(PDFResourceLimitError, match='PDF_TEXT_TOO_LARGE'):
        extract_text_from_pdf_bytes(pdf())


@pytest.mark.skipif(__import__('sys').platform != 'linux', reason='Linux enforces RLIMIT_AS')
def test_linux_memory_limit_fails_closed(monkeypatch):
    monkeypatch.setattr(boundary, 'PDF_EXTRACTION_MEMORY_MB', 1)
    with pytest.raises(PDFResourceLimitError, match='PDF_PROCESSING_LIMIT'):
        extract_text_from_pdf_bytes(pdf())
