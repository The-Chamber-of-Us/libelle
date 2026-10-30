# Backend – Libelle

This directory will contain the FastAPI backend for Libelle, including:

- Intake endpoints
- Resume parsing logic
- Google Drive / Sheets integration
- Matching and scoring services

Implementation is in progress.

See the root README for system architecture.

### Public PDF resource ceilings

Public intake and background byte-based PDF extraction use a disposable subprocess.
Limits are positive integer environment variables (invalid values fail startup):

| Variable | Default | Meaning |
| --- | --- | --- |
| `MAX_PDF_MB` | 5 | Existing upload size limit in MiB; HTTP 413 `FILE_TOO_LARGE` |
| `MAX_PDF_PAGES` | 50 | Pages, checked before text extraction |
| `MAX_PDF_TEXT_BYTES` | 1048576 | Total UTF-8 text bytes, including inserted separators |
| `PDF_EXTRACTION_TIMEOUT_SECONDS` | 10 | Wall time for each child, including startup |
| `PDF_EXTRACTION_MEMORY_MB` | 512 | Child address-space limit in MiB |
| `PDF_EXTRACTION_MAX_CONCURRENT` | 2 | Active extraction children per application/worker process |

Unix `resource` limits cap output-file size and disable core files. Linux also
enforces the address-space ceiling; macOS development retains wall-time/output
limits but cannot enforce `RLIMIT_AS`. Platforms without `resource` fail closed.
Run production on Linux to enforce all ceilings.
The parent kills and reaps timed-out children, discards diagnostics, bounds result
reads, and deletes temporary files on success or failure. JSON/layout output has a
separate ceiling of 32 times the text limit plus 1024 bytes per allowed page.
Native allocations within a single page are contained by the process memory/time
ceilings; extracted-text checks occur after each page. Local path-based benchmark
extraction is unchanged.

Limit rejections return the established `detail: {status: "error", code, message}`
contract: HTTP 400 `PDF_TOO_MANY_PAGES`, `PDF_TEXT_TOO_LARGE`,
`PDF_EXTRACTION_TIMEOUT`, or `PDF_PROCESSING_LIMIT`. Saturation rejects immediately
with HTTP 503 `PDF_EXTRACTION_BUSY` instead of queuing children. Malformed and
password-protected PDFs remain HTTP 400 `INVALID_PDF`. All intake checks finish
before Drive uploads, Sheets writes, or parser-job creation. The upload handler
reads at most the size limit plus one byte and runs synchronous work off the event
loop. Multipart transport/spooling limits still belong at the reverse proxy;
concurrency limits are per process, not distributed rate limiting.
