"""
EXPERIMENTAL — layout-aware extraction prototype for issue #275.

Builds on the column-detection and header-scoping logic validated in the
PR #274 observation-only spike (backend/benchmarks/layout_spike/), hardened
with safeguards to avoid the false-positive column detections documented
in PYMUPDF_XY_MULTICOLUMN_FINDINGS.md (Daniel Foster, Rohan Mehta,
Jadhav_Riya).

NOT wired into production. NOT imported by parser.py, intake_service.py,
or any production code path. Only reachable via the explicit `enabled`
flag on extract_text_layout_aware(), which defaults to False.

Place at: backend/benchmarks/layout_aware_extraction/layout_aware_extraction.py
"""

from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

# Safeguard defaults — see PYMUPDF_XY_MULTICOLUMN_FINDINGS.md section 4/6
# and LAYOUT_AWARE_EXTRACTION_RECOMMENDATION.md section 7 for rationale.
MIN_BLOCKS_PER_LANE = 3
MIN_VERTICAL_OVERLAP_RATIO = 0.3
EDGE_CONFINEMENT_MARGIN_RATIO = 0.15
MIN_HEADERS_ACROSS_LANES = 2
GAP_BOUNDARY_RATIO = 0.10


# ---------------------------------------------------------------------------
# Header detection (unchanged from spike)
# ---------------------------------------------------------------------------

def _is_header(text: str) -> bool:
    cleaned = text.strip().rstrip(":").lower()
    if cleaned.replace(" ", "").replace("&", "").isupper() and len(cleaned) > 2:
        return True
    return cleaned in HEADER_KEYWORDS


# ---------------------------------------------------------------------------
# Block extraction (dict view -> flat records with text)
# ---------------------------------------------------------------------------

def _get_flat_blocks(page: fitz.Page) -> list[tuple[float, float, float, float, str]]:
    """Flatten get_text('dict') into (x0, y0, x1, y1, text) tuples."""
    data = page.get_text("dict")
    flat = []
    for block in data["blocks"]:
        if block["type"] != 0:
            continue
        bbox = block["bbox"]
        text = " ".join(
            span["text"] for line in block["lines"] for span in line["spans"]
        ).strip()
        if text:
            flat.append((bbox[0], bbox[1], bbox[2], bbox[3], text))
    return flat


# ---------------------------------------------------------------------------
# Safeguards
# ---------------------------------------------------------------------------

def _vertical_overlap_ratio(
    left: list[tuple], right: list[tuple], page_height: float
) -> float:
    """
    Fraction of page height where left-lane and right-lane content
    vertically overlap. Real two-column layouts have sustained overlap;
    an isolated header/contact block sitting alone at one y-position
    does not.
    """
    if not left or not right:
        return 0.0
    l_y0 = min(b[1] for b in left)
    l_y1 = max(b[3] for b in left)
    r_y0 = min(b[1] for b in right)
    r_y1 = max(b[3] for b in right)
    overlap = max(0.0, min(l_y1, r_y1) - max(l_y0, r_y0))
    return overlap / page_height if page_height else 0.0


def _is_confined_to_edge(
    blocks: list[tuple], page_height: float, margin_ratio: float
) -> bool:
    """
    True if a lane's content is squeezed into a thin vertical band
    (top or bottom margin) rather than spanning a meaningful portion
    of the page. Catches isolated name/contact blocks masquerading
    as a second column (Daniel Foster, Rohan Mehta cases).
    """
    if not blocks:
        return True
    y0 = min(b[1] for b in blocks)
    y1 = max(b[3] for b in blocks)
    return (y1 - y0) < page_height * margin_ratio


def _count_headers(blocks: list[tuple]) -> int:
    return sum(1 for b in blocks if _is_header(b[4]))


def _detect_column_boundary_raw(
    blocks: list[tuple], page_width: float
) -> Optional[float]:
    """Same gap-based boundary detection as the spike, unmodified."""
    x0_values = sorted(set(round(b[0], 1) for b in blocks))
    if not x0_values:
        return None

    max_gap, boundary = 0, None
    for i in range(1, len(x0_values)):
        gap = x0_values[i] - x0_values[i - 1]
        if gap > max_gap:
            max_gap = gap
            boundary = (x0_values[i] + x0_values[i - 1]) / 2

    if boundary and max_gap > page_width * GAP_BOUNDARY_RATIO:
        left = [b for b in blocks if b[0] < boundary]
        right = [b for b in blocks if b[0] >= boundary]
        if left and right:
            return boundary

    midpoint = page_width * 0.5
    left = [b for b in blocks if b[0] < midpoint]
    right = [b for b in blocks if b[0] >= midpoint]
    if left and right and len(right) >= 2:
        return midpoint

    return None


def detect_column_boundary(
    blocks: list[tuple],
    page_width: float,
    page_height: float,
    min_blocks_per_lane: int = MIN_BLOCKS_PER_LANE,
    min_vertical_overlap_ratio: float = MIN_VERTICAL_OVERLAP_RATIO,
    edge_margin_ratio: float = EDGE_CONFINEMENT_MARGIN_RATIO,
    min_headers_across_lanes: int = MIN_HEADERS_ACROSS_LANES,
) -> tuple[Optional[float], str]:
    """
    Hardened column-boundary detection. Returns (boundary, reason).
    boundary is None if any safeguard rejects the candidate split —
    callers should fall back to single-column (production) extraction.

    Safeguards applied, in order:
      1. Minimum block count per lane
      2. Vertical overlap between lanes
      3. Edge confinement exclusion (isolated header/contact block)
      4. Sustained structure requirement (headers present in both lanes)
    """
    candidate = _detect_column_boundary_raw(blocks, page_width)
    if candidate is None:
        return None, "no_candidate_boundary"

    left = [b for b in blocks if b[0] < candidate]
    right = [b for b in blocks if b[0] >= candidate]

    # Safeguard 1: minimum block count per lane
    if len(left) < min_blocks_per_lane or len(right) < min_blocks_per_lane:
        return None, f"insufficient_blocks_per_lane(left={len(left)},right={len(right)})"

    # Safeguard 2: vertical overlap validation
    overlap = _vertical_overlap_ratio(left, right, page_height)
    if overlap < min_vertical_overlap_ratio:
        return None, f"insufficient_vertical_overlap({overlap:.2f})"

    # Safeguard 3: isolated header/contact block exclusion
    if _is_confined_to_edge(left, page_height, edge_margin_ratio) or \
       _is_confined_to_edge(right, page_height, edge_margin_ratio):
        return None, "edge_confined_lane"

    # Safeguard 4: sustained two-column structure — require headers in
    # BOTH lanes, not just a total count, since the Jadhav_Riya failure
    # had all headers land in one lane and all content in the other.
    left_headers = _count_headers(left)
    right_headers = _count_headers(right)
    if left_headers < 1 or right_headers < 1:
        return None, f"headers_not_sustained_across_lanes(left={left_headers},right={right_headers})"
    if left_headers + right_headers < min_headers_across_lanes:
        return None, f"insufficient_total_headers({left_headers + right_headers})"

    return candidate, "accepted"


# ---------------------------------------------------------------------------
# Text assembly
# ---------------------------------------------------------------------------

def _sort_single_column(blocks: list[tuple]) -> list[tuple]:
    """Matches current production ordering: global (y0, x0) sort."""
    return sorted(blocks, key=lambda b: (b[1], b[0]))


def _header_scoped_text(blocks: list[tuple], boundary: float) -> str:
    """
    Split into lanes by boundary, sort each lane by y0, then group
    content under the nearest header above it within the same lane.
    Left lane emitted before right lane.
    """
    left = sorted([b for b in blocks if b[0] < boundary], key=lambda b: b[1])
    right = sorted([b for b in blocks if b[0] >= boundary], key=lambda b: b[1])

    output = []
    for lane in (left, right):
        current_header = None
        for item in lane:
            text = item[4]
            if _is_header(text):
                current_header = text.strip()
                output.append(current_header)
            else:
                output.append(text)
    return "\n".join(output)


# ---------------------------------------------------------------------------
# Main entry point — gated behind explicit experimental flag
# ---------------------------------------------------------------------------

def extract_text_layout_aware(page: fitz.Page, enabled: bool = False) -> dict:
    """
    Returns:
        {
            "text": str,
            "layout_aware_used": bool,   # True only if safeguards accepted a split
            "reason": str,               # why layout-aware was/wasn't used
        }

    enabled=False (default) always falls back to current production
    ordering — this function is inert unless explicitly turned on by
    the caller (e.g. the benchmark harness), and is never called from
    any production code path.
    """
    flat = _get_flat_blocks(page)

    if not enabled:
        text = "\n".join(b[4] for b in _sort_single_column(flat))
        return {"text": text, "layout_aware_used": False, "reason": "flag_disabled"}

    boundary, reason = detect_column_boundary(
        flat, page.rect.width, page.rect.height
    )

    if boundary is None:
        # Low-confidence fallback: behave exactly like production.
        text = "\n".join(b[4] for b in _sort_single_column(flat))
        return {"text": text, "layout_aware_used": False, "reason": reason}

    text = _header_scoped_text(flat, boundary)
    return {"text": text, "layout_aware_used": True, "reason": reason}


def extract_text_from_pdf_layout_aware(pdf_path: Path, enabled: bool = False) -> dict:
    """Multi-page wrapper. Aggregates per-page results."""
    doc = fitz.open(str(pdf_path))
    try:
        page_results = [extract_text_layout_aware(p, enabled=enabled) for p in doc]
    finally:
        doc.close()

    return {
        "text": "\n".join(r["text"] for r in page_results),
        "layout_aware_used": any(r["layout_aware_used"] for r in page_results),
        "reasons": [r["reason"] for r in page_results],
    }