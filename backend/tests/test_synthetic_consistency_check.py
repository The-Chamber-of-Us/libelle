import sys
from pathlib import Path

GENERATOR_DIR = Path(__file__).parent.parent / "benchmarks" / "synthetic" / "generator"
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

from consistency_check import _case_id  # noqa: E402


def test_case_id_prefers_v1_submission_id():
    gold = {"submission_id": "syn_000_known", "resume_id": "should_not_win"}
    assert _case_id(gold, Path("syn_000_known.pdf")) == "syn_000_known"


def test_case_id_falls_back_to_v2_resume_id():
    gold = {"resume_id": "syn_000_known"}
    assert _case_id(gold, Path("syn_000_known.pdf")) == "syn_000_known"


def test_case_id_falls_back_to_filename_stem():
    gold = {}
    assert _case_id(gold, Path("syn_000_known.pdf")) == "syn_000_known"
