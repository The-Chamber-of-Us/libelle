"""
EXPLORATORY — layout spike only. Do not wire into production.

Run directly from backend/:
    python test_layout_extraction.py benchmarks/resumes/multi_col_02.pdf
    python test_layout_extraction.py resume1.pdf resume2.pdf

Or import into another script:
    from test_layout_extraction import test_extraction
    test_extraction("benchmarks/resumes/multi_col_02.pdf")
"""

from pathlib import Path
import fitz

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


def _is_header(text: str) -> bool:
    cleaned = text.strip().rstrip(":").lower()
    if cleaned.replace(" ", "").replace("&", "").isupper() and len(cleaned) > 2:
        return True
    return cleaned in HEADER_KEYWORDS


def _detect_boundary(blocks: list, page_width: float) -> float | None:
    x0_values = sorted(set(round(b[0], 1) for b in blocks))
    if not x0_values:
        return None
    max_gap, boundary = 0, None
    for i in range(1, len(x0_values)):
        gap = x0_values[i] - x0_values[i - 1]
        if gap > max_gap:
            max_gap = gap
            boundary = (x0_values[i] + x0_values[i - 1]) / 2
    if boundary and max_gap > page_width * 0.10:
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


def column_aware(page: fitz.Page) -> str:
    blocks = [b for b in page.get_text("blocks") if b[6] == 0]
    boundary = _detect_boundary([(b[0], b[1], b[2], b[3]) for b in blocks], page.rect.width)
    if boundary is None:
        sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
        note = "[single-column]"
    else:
        left = sorted([b for b in blocks if b[0] < boundary], key=lambda b: b[1])
        right = sorted([b for b in blocks if b[0] >= boundary], key=lambda b: b[1])
        sorted_blocks = left + right
        note = f"[multi-column, boundary x={boundary:.1f}]"
    return note + "\n" + "\n".join(b[4].strip() for b in sorted_blocks)


def header_scoped(page: fitz.Page) -> str:
    data = page.get_text("dict")
    blocks = [b for b in data["blocks"] if b["type"] == 0]

    flat = []
    for block in blocks:
        bbox = block["bbox"]
        text = " ".join(
            span["text"] for line in block["lines"] for span in line["spans"]
        ).strip()
        flat.append((bbox[0], bbox[1], bbox[2], bbox[3], text))

    boundary = _detect_boundary([(f[0], f[1], f[2], f[3]) for f in flat], page.rect.width)

    if boundary is None:
        lanes = [sorted(flat, key=lambda b: b[1])]
        labels = ["[single column]"]
    else:
        lanes = [
            sorted([f for f in flat if f[0] < boundary], key=lambda b: b[1]),
            sorted([f for f in flat if f[0] >= boundary], key=lambda b: b[1]),
        ]
        labels = [f"[left column x < {boundary:.1f}]", f"[right column x >= {boundary:.1f}]"]

    output = []
    for label, lane in zip(labels, lanes):
        output.append(label)
        current_header = "[no header]"
        sections: dict[str, list[str]] = {}
        for item in lane:
            text = item[4]
            if not text:
                continue
            if _is_header(text):
                current_header = text.strip()
                if current_header not in sections:
                    sections[current_header] = []
            else:
                sections.setdefault(current_header, []).append(text)
        for header, contents in sections.items():
            output.append(f"  [{header}]")
            for c in contents:
                output.append(f"    {c}")
    return "\n".join(output)


def test_extraction(pdf_path: str) -> None:
    path = Path(pdf_path)
    doc = fitz.open(str(path))
    try:
        for i, page in enumerate(doc):
            print(f"\n{'='*60}")
            print(f"FILE: {path.name} — Page {i+1}")
            print(f"{'='*60}")

            print("\n[COLUMN-AWARE]")
            print(column_aware(page))

            print("\n[HEADER-SCOPED]")
            print(header_scoped(page))
    finally:
        doc.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python test_layout_extraction.py <pdf_path> [pdf_path2 ...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        test_extraction(arg)