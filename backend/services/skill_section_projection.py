"""Conservative, skill-only projection from positioned PDF text.

General parsing continues to use the extractor's established flattened text.
This module uses the positioned sidecar only to establish ownership of text
under explicit skill headings. Ambiguous layouts retain the existing
first-skill-section behavior.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Sequence

from parser import (
    _is_section_header,
    _is_skill_start_header,
    _is_skill_stop_header,
)
from services.pdf_text_extraction import (
    ExtractedPdfText,
    PositionedTextBlock,
    PositionedTextPage,
)


MIN_BLOCKS_PER_LANE = 3
MIN_VERTICAL_OVERLAP_RATIO = 0.30
EDGE_CONFINEMENT_RATIO = 0.15
GAP_BOUNDARY_RATIO = 0.10
DOMINANT_START_RATIO = 0.75


class LayoutKind(Enum):
    SINGLE_COLUMN = auto()
    MULTI_COLUMN = auto()
    AMBIGUOUS = auto()


@dataclass(frozen=True)
class SkillSectionProjection:
    text: str
    layout: LayoutKind


@dataclass(frozen=True)
class _PageDecision:
    layout: LayoutKind
    boundary: Optional[float] = None


def _is_layout_header(block: PositionedTextBlock) -> bool:
    return any(
        _is_section_header(line)
        or _is_skill_start_header(line)
        or _is_skill_stop_header(line)
        for line in block.text.splitlines()
    )


def _raw_boundary(
    blocks: Sequence[PositionedTextBlock], page_width: float
) -> Optional[float]:
    if not blocks:
        return None

    starts = sorted({round(block.x0, 1) for block in blocks})
    largest_gap = 0.0
    boundary = None
    for left, right in zip(starts, starts[1:]):
        gap = right - left
        if gap > largest_gap:
            largest_gap = gap
            boundary = (left + right) / 2

    if boundary is not None and largest_gap > page_width * GAP_BOUNDARY_RATIO:
        if any(block.x0 < boundary for block in blocks) and any(
            block.x0 >= boundary for block in blocks
        ):
            return boundary

    midpoint = page_width * 0.5
    left = [block for block in blocks if block.x0 < midpoint]
    right = [block for block in blocks if block.x0 >= midpoint]
    if left and len(right) >= 2:
        return midpoint
    return None


def _vertical_overlap(
    left: Sequence[PositionedTextBlock],
    right: Sequence[PositionedTextBlock],
    page_height: float,
) -> float:
    if not left or not right or not page_height:
        return 0.0
    overlap = max(
        0.0,
        min(max(block.y1 for block in left), max(block.y1 for block in right))
        - max(min(block.y0 for block in left), min(block.y0 for block in right)),
    )
    return overlap / page_height


def _is_edge_confined(
    blocks: Sequence[PositionedTextBlock], page_height: float
) -> bool:
    if not blocks:
        return True
    span = max(block.y1 for block in blocks) - min(block.y0 for block in blocks)
    return span < page_height * EDGE_CONFINEMENT_RATIO


def _guarded_boundary(page: PositionedTextPage) -> Optional[float]:
    boundary = _raw_boundary(page.blocks, page.width)
    if boundary is None:
        return None

    left = [block for block in page.blocks if block.x0 < boundary]
    right = [block for block in page.blocks if block.x0 >= boundary]
    if len(left) < MIN_BLOCKS_PER_LANE or len(right) < MIN_BLOCKS_PER_LANE:
        return None
    if _vertical_overlap(left, right, page.height) < MIN_VERTICAL_OVERLAP_RATIO:
        return None
    if _is_edge_confined(left, page.height) or _is_edge_confined(right, page.height):
        return None
    if not any(_is_layout_header(block) for block in left):
        return None
    if not any(_is_layout_header(block) for block in right):
        return None
    return boundary


def _dominant_start_ratio(page: PositionedTextPage) -> float:
    if not page.blocks:
        return 0.0
    body = [
        block
        for block in page.blocks
        if block.x1 - block.x0 < page.width * 0.75
    ]
    if len(body) < 3:
        body = list(page.blocks)
    starts = [block.x0 for block in body]
    band = page.width * 0.08
    return max(
        sum(abs(other - start) <= band for other in starts)
        for start in starts
    ) / len(starts)


def _classify_page(page: PositionedTextPage) -> _PageDecision:
    boundary = _guarded_boundary(page)
    if boundary is not None:
        return _PageDecision(LayoutKind.MULTI_COLUMN, boundary)

    raw_boundary = _raw_boundary(page.blocks, page.width)
    if raw_boundary is not None:
        left = [block for block in page.blocks if block.x0 < raw_boundary]
        right = [block for block in page.blocks if block.x0 >= raw_boundary]
        isolated_minor_lane = (
            len(left) <= 1
            and _is_edge_confined(left, page.height)
            and not _is_edge_confined(right, page.height)
        ) or (
            len(right) <= 1
            and _is_edge_confined(right, page.height)
            and not _is_edge_confined(left, page.height)
        )
        if min(len(left), len(right)) <= 1 and isolated_minor_lane:
            return _PageDecision(LayoutKind.SINGLE_COLUMN)
        return _PageDecision(LayoutKind.AMBIGUOUS)

    if _dominant_start_ratio(page) >= DOMINANT_START_RATIO:
        return _PageDecision(LayoutKind.SINGLE_COLUMN)
    return _PageDecision(LayoutKind.AMBIGUOUS)


def _lines(blocks: Sequence[PositionedTextBlock]) -> List[str]:
    result = []
    for block in sorted(blocks, key=lambda item: (item.y0, item.x0)):
        result.extend(line.strip() for line in block.text.splitlines() if line.strip())
    return result


def _page_streams(
    page: PositionedTextPage, decision: _PageDecision
) -> List[List[str]]:
    if decision.layout is not LayoutKind.MULTI_COLUMN or decision.boundary is None:
        return [_lines(page.blocks)]

    shared = []
    left = []
    right = []
    for block in page.blocks:
        is_full_width_heading = (
            block.x1 - block.x0 >= page.width * 0.70 and _is_layout_header(block)
        )
        if is_full_width_heading:
            shared.append(block)
        elif block.x0 < decision.boundary:
            left.append(block)
        else:
            right.append(block)

    return [
        _lines([*left, *shared]),
        _lines([*right, *shared]),
    ]


def _collect(stream: Sequence[str], max_sections: Optional[int]) -> List[str]:
    collected = []
    capturing = False
    section_count = 0
    for line in stream:
        if _is_skill_start_header(line):
            if max_sections is not None and section_count >= max_sections:
                capturing = False
                continue
            section_count += 1
            capturing = True
            continue
        if capturing and _is_skill_stop_header(line):
            capturing = False
            continue
        if capturing:
            collected.append(line)
    return collected


def project_skill_sections(extracted: ExtractedPdfText) -> SkillSectionProjection:
    """Produce tokenizer-compatible text owned by explicit skill sections."""
    decisions = tuple(_classify_page(page) for page in extracted.positioned_pages)
    if not decisions or any(
        decision.layout is LayoutKind.AMBIGUOUS for decision in decisions
    ):
        layout = LayoutKind.AMBIGUOUS
    elif any(decision.layout is LayoutKind.MULTI_COLUMN for decision in decisions):
        layout = LayoutKind.MULTI_COLUMN
    else:
        layout = LayoutKind.SINGLE_COLUMN

    content = []
    if layout is LayoutKind.AMBIGUOUS:
        production_order = [
            line.strip() for line in extracted.text.splitlines() if line.strip()
        ]
        content = _collect(production_order, max_sections=1)
    elif layout is LayoutKind.SINGLE_COLUMN:
        single_stream = []
        for page in extracted.positioned_pages:
            single_stream.extend(_lines(page.blocks))
        content = _collect(single_stream, max_sections=None)
    else:
        for page, decision in zip(extracted.positioned_pages, decisions):
            for stream in _page_streams(page, decision):
                content.extend(_collect(stream, max_sections=None))

    text = "SKILLS"
    if content:
        text += "\n" + "\n".join(content)
    return SkillSectionProjection(
        text=text,
        layout=layout,
    )
