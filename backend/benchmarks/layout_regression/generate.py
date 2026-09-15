"""Render the small, explicitly annotated ownership corpus with PyMuPDF."""

import argparse
import json
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parent


def load_cases():
    return json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))


def render_pdf(case):
    with fitz.open() as document:
        page = document.new_page(width=640, height=820)
        for block in case["blocks"]:
            x = block["x"]
            if block.get("align") == "right":
                x -= fitz.get_text_length(
                    block["text"], fontname="helv", fontsize=block["size"]
                )
            page.insert_text(
                (x, block["y"]), block["text"],
                fontsize=block["size"], fontname="helv",
            )
        # Omit randomized file IDs and timestamps for byte-identical replay
        # with the repository's pinned PyMuPDF version.
        return document.tobytes(no_new_id=True, deflate=True)


def generate(output):
    pdf_dir, gold_dir = output / "pdfs", output / "golden_json"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    for case in load_cases():
        (pdf_dir / f'{case["id"]}.pdf').write_bytes(render_pdf(case))
        gold = {
            "submission_id": case["id"],
            "skills": case["skills"],
            "location": {},
            "notes": case["purpose"],
        }
        (gold_dir / f'{case["id"]}.json').write_text(
            json.dumps(gold, indent=2) + "\n", encoding="utf-8"
        )
    return pdf_dir, gold_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "out")
    generate(parser.parse_args().output)
