"""
EXPLORATORY SCRIPT — layout spike only.
Do NOT wire into production code or import from parser/intake.

Inspects PyMuPDF block/coordinate data from resume PDFs to evaluate
whether x/y metadata can improve reading order for multi-column layouts.

Uses only fitz (PyMuPDF) — no new dependencies.

Place at: backend/benchmarks/layout_spike/inspect_pymupdf_layout.py
Run from: backend/
Usage:
    python benchmarks/layout_spike/inspect_pymupdf_layout.py <pdf_path>
"""

import sys
from pathlib import Path
import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Known resume section header keywords (lowercase).
HEADER_KEYWORDS = {
    "summary", "objective", "about", "about me",
    "experience", "work experience", "professional experience",
    "education", "academic background",
    "skills", "technical skills", "core skills", "soft skills",
    "tools", "languages",
    "projects", "personal projects", "projects & personal experience",
    "certifications", "certificates", "awards",
    "references", "contact",
}

# If x0 of a block is less than this fraction of page width,
# it's considered left-column. Otherwise right-column.
# Only used when two clusters are detected.
MIDPOINT_FALLBACK_RATIO = 0.5


# ---------------------------------------------------------------------------
# Layout detection helpers
# ---------------------------------------------------------------------------

def _is_header_block(text: str) -> bool:
    """Return True if the block text looks like a resume section header."""
    cleaned = text.strip().rstrip(":").lower()
    # ALL CAPS check
    if cleaned.replace(" ", "").replace("&", "").isupper() and len(cleaned) > 2:
        return True
    # Known keyword match
    if cleaned in HEADER_KEYWORDS:
        return True
    return False


def _detect_column_boundary(blocks: list, page_width: float) -> float | None:
    """
    Use x0 values of text blocks to detect a column split boundary.
    Returns the x boundary (float) if two clear clusters are found,
    otherwise returns None (single column or unclear layout).

    Strategy: collect all x0 values, sort them, look for a gap
    that suggests a column boundary. Falls back to page midpoint
    if no clear gap is found but blocks clearly span both halves.
    """
    x0_values = sorted(set(round(b[0], 1) for b in blocks))

    if not x0_values:
        return None

    # Find the largest gap between consecutive x0 values
    max_gap = 0
    boundary = None
    for i in range(1, len(x0_values)):
        gap = x0_values[i] - x0_values[i - 1]
        if gap > max_gap:
            max_gap = gap
            boundary = (x0_values[i] + x0_values[i - 1]) / 2

    # Only treat as multi-column if:
    # - the gap is meaningfully large (>10% of page width)
    # - blocks exist on both sides of the boundary
    if boundary and max_gap > page_width * 0.10:
        left_blocks = [b for b in blocks if b[0] < boundary]
        right_blocks = [b for b in blocks if b[0] >= boundary]
        if left_blocks and right_blocks:
            return boundary

    # Fallback: check if blocks genuinely span both halves
    midpoint = page_width * MIDPOINT_FALLBACK_RATIO
    left = [b for b in blocks if b[0] < midpoint]
    right = [b for b in blocks if b[0] >= midpoint]
    if left and right and len(right) >= 2:
        return midpoint

    return None  # single column


def _sort_single_column(blocks: list) -> list:
    """Sort blocks top-to-bottom, left-to-right (current production behavior)."""
    return sorted(blocks, key=lambda b: (b[1], b[0]))


def _sort_multi_column(blocks: list, boundary: float) -> list:
    """
    Split blocks into left/right lanes by boundary x value.
    Sort each lane independently by y0, then concatenate:
    left lane first, then right lane.

    This avoids interleaving that occurs when two columns are
    sorted globally by y0.
    """
    left = sorted([b for b in blocks if b[0] < boundary], key=lambda b: b[1])
    right = sorted([b for b in blocks if b[0] >= boundary], key=lambda b: b[1])
    return left + right


# ---------------------------------------------------------------------------
# Extraction modes
# ---------------------------------------------------------------------------

def extract_plain_text(page: fitz.Page) -> str:
    """get_text('text') — raw storage order, no sorting. Baseline."""
    return page.get_text("text")


def extract_blocks_current(page: fitz.Page) -> str:
    """
    Current production behavior from pdf_text_extraction.py:
    get_text('blocks') sorted by (y0, x0) globally.
    """
    blocks = page.get_text("blocks")
    text_blocks = [b for b in blocks if b[6] == 0]
    text_blocks.sort(key=lambda b: (b[1], b[0]))
    return "\n".join(b[4].strip() for b in text_blocks)


def extract_blocks_column_aware(page: fitz.Page) -> str:
    """
    Column-aware extraction using get_text('blocks') + x0 clustering.
    Detects multi-column layout and sorts each column independently.
    """
    blocks = page.get_text("blocks")
    text_blocks = [b for b in blocks if b[6] == 0]

    boundary = _detect_column_boundary(
        [(b[0], b[1], b[2], b[3]) for b in text_blocks],
        page.rect.width
    )

    if boundary is None:
        sorted_blocks = _sort_single_column(text_blocks)
        layout_note = "[single-column detected]"
    else:
        sorted_blocks = _sort_multi_column(text_blocks, boundary)
        layout_note = f"[multi-column detected, boundary x={boundary:.1f}]"

    text = "\n".join(b[4].strip() for b in sorted_blocks)
    return f"{layout_note}\n{text}"


def extract_dict_view(page: fitz.Page) -> str:
    """
    get_text('dict') — shows block/line/span structure with bboxes.
    Useful for inspecting what coordinate data looks like per block.
    Prints a condensed view: block bbox + first line of text per block.
    """
    data = page.get_text("dict")
    lines = []
    for block in data["blocks"]:
        if block["type"] != 0:
            continue
        bbox = block["bbox"]
        block_text = " ".join(
            span["text"]
            for line in block["lines"]
            for span in line["spans"]
        ).strip()
        is_header = _is_header_block(block_text)
        header_flag = " ← HEADER" if is_header else ""
        lines.append(
            f"  bbox=({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})"
            f"  text={block_text[:80]!r}{header_flag}"
        )
    return "\n".join(lines)


def extract_table_view(page: fitz.Page) -> str:
    """
    page.find_tables() — checks whether PyMuPDF detects any table structure.
    Useful for resumes that use invisible table borders for two-column layout.
    """
    try:
        tabs = page.find_tables()
        if not tabs.tables:
            return "  No tables detected."
        results = []
        for i, table in enumerate(tabs.tables):
            results.append(f"  Table {i+1}: bbox={table.bbox}")
            rows = table.extract()
            for row in rows[:5]:  # show first 5 rows only
                results.append(f"    row: {row}")
            if len(rows) > 5:
                results.append(f"    ... ({len(rows)} rows total)")
        return "\n".join(results)
    except Exception as e:
        return f"  find_tables() error: {e}"


def extract_header_scoped(page: fitz.Page) -> str:
    """
    Header-scoped extraction using get_text('dict') + column detection.

    For each column lane:
    - identify header blocks
    - group content blocks under their nearest header above them
      within the same lane

    This is the 'only grab what's under a header' idea — content
    stays associated with its visual header, not interleaved with
    content from adjacent columns.
    """
    data = page.get_text("dict")
    blocks = [b for b in data["blocks"] if b["type"] == 0]

    # Build flat list of (x0, y0, x1, y1, text) for column detection
    flat = []
    for block in blocks:
        bbox = block["bbox"]
        text = " ".join(
            span["text"]
            for line in block["lines"]
            for span in line["spans"]
        ).strip()
        flat.append((bbox[0], bbox[1], bbox[2], bbox[3], text, block))

    boundary = _detect_column_boundary(
        [(f[0], f[1], f[2], f[3]) for f in flat],
        page.rect.width
    )

    if boundary is None:
        lanes = [sorted(flat, key=lambda b: b[1])]
        lane_labels = ["[single column]"]
    else:
        left_lane = sorted([f for f in flat if f[0] < boundary], key=lambda b: b[1])
        right_lane = sorted([f for f in flat if f[0] >= boundary], key=lambda b: b[1])
        lanes = [left_lane, right_lane]
        lane_labels = [f"[left column, x < {boundary:.1f}]", f"[right column, x >= {boundary:.1f}]"]

    output = []
    for label, lane in zip(lane_labels, lanes):
        output.append(label)
        current_header = "[no header]"
        sections: dict[str, list[str]] = {}

        for item in lane:
            text = item[4]
            if not text:
                continue
            if _is_header_block(text):
                current_header = text.strip()
                if current_header not in sections:
                    sections[current_header] = []
            else:
                if current_header not in sections:
                    sections[current_header] = []
                sections[current_header].append(text)

        for header, contents in sections.items():
            output.append(f"  [{header}]")
            for c in contents:
                output.append(f"    {c[:120]}")

    return "\n".join(output)


# ---------------------------------------------------------------------------
# Main inspection runner
# ---------------------------------------------------------------------------

def inspect_resume(pdf_path: Path) -> None:
    print("=" * 70)
    print(f"FILE: {pdf_path.name}")
    print("=" * 70)

    doc = fitz.open(str(pdf_path))
    try:
        for page_num, page in enumerate(doc):
            print(f"\n--- Page {page_num + 1} ---")
            print(f"Page dimensions: {page.rect.width:.1f} x {page.rect.height:.1f}")

            print("\n[1] PLAIN TEXT (get_text('text') — raw storage order)")
            print(extract_plain_text(page))

            print("\n[2] BLOCKS CURRENT (production: get_text('blocks') sorted by y0,x0)")
            print(extract_blocks_current(page))

            print("\n[3] BLOCKS COLUMN-AWARE (x0 clustering + per-lane sort)")
            print(extract_blocks_column_aware(page))

            print("\n[4] DICT VIEW (get_text('dict') — bbox per block + header detection)")
            print(extract_dict_view(page))

            print("\n[5] TABLE DETECTION (page.find_tables())")
            print(extract_table_view(page))

            print("\n[6] HEADER-SCOPED (column lanes + content grouped under headers)")
            print(extract_header_scoped(page))

    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_pymupdf_layout.py <pdf_path> [pdf_path2 ...]")
        sys.exit(1)

    for path_arg in sys.argv[1:]:
        pdf_path = Path(path_arg)
        if not pdf_path.exists():
            print(f"File not found: {pdf_path}")
            continue
        inspect_resume(pdf_path)
        print()