"""Private subprocess entrypoint. Apply OS ceilings before importing PyMuPDF."""
import json
import sys
from pathlib import Path


def main():
    source, output = sys.argv[1:3]
    pages, text_bytes, memory_mb, output_bytes = map(int, sys.argv[3:])
    # Production requires Unix resource limits; unsupported platforms fail closed.
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_bytes, output_bytes))
    # macOS does not support RLIMIT_AS; wall-time/output ceilings still apply.
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024**2, memory_mb * 1024**2))

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from dataclasses import asdict
    import fitz
    from services.pdf_text_extraction import _extract_pdf_text_from_fitz_doc, PDFResourceLimitError

    try:
        with fitz.open(source) as doc:
            if doc.needs_pass:
                data = {'error': 'PASSWORD_PROTECTED_PDF'}
            else:
                data = asdict(_extract_pdf_text_from_fitz_doc(
                    doc, max_pages=pages, max_text_bytes=text_bytes))
    except PDFResourceLimitError as exc:
        data = {'error': exc.code}
    except MemoryError:
        data = {'error': 'PDF_PROCESSING_LIMIT'}
    except Exception:
        data = {'error': 'INVALID_PDF'}
    Path(output).write_text(json.dumps(data), encoding='utf-8')


if __name__ == '__main__':
    main()
