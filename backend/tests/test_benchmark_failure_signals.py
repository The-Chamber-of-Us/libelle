import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmark import (
    is_fn_heavy,
    is_fp_heavy,
    has_zero_tp,
    total_error_count,
    is_high_total_error,
    is_low_f1,
    possible_resolver_mismatch,
    compute_failure_signals,
)


def test_is_fn_heavy_true():
    row = {"fp_count": 1, "fn_count": 5}
    assert is_fn_heavy(row) is True


def test_is_fn_heavy_false_when_equal():
    row = {"fp_count": 3, "fn_count": 3}
    assert is_fn_heavy(row) is False


def test_is_fp_heavy_true():
    row = {"fp_count": 6, "fn_count": 2}
    assert is_fp_heavy(row) is True


def test_has_zero_tp_true():
    row = {"tp_count": 0, "fn_count": 4}
    assert has_zero_tp(row) is True


def test_has_zero_tp_false_when_no_fn():
    row = {"tp_count": 0, "fn_count": 0}
    assert has_zero_tp(row) is False


def test_total_error_count():
    row = {"fp_count": 3, "fn_count": 4}
    assert total_error_count(row) == 7


def test_is_high_total_error_true():
    row = {"fp_count": 4, "fn_count": 3}
    assert is_high_total_error(row, threshold=5) is True


def test_is_high_total_error_false():
    row = {"fp_count": 1, "fn_count": 1}
    assert is_high_total_error(row, threshold=5) is False


def test_is_low_f1_true():
    row = {"tp_count": 1, "fp_count": 2, "fn_count": 2, "f1": 0.2}
    assert is_low_f1(row, threshold=0.3) is True


def test_low_f1_ignores_empty_row():
    row = {"tp_count": 0, "fp_count": 0, "fn_count": 0, "f1": 0.0}
    assert is_low_f1(row) is False


def test_resolver_mismatch_flags_large_gap():
    skills_row = {"f1": 0.20}
    resolved_row = {"f1": 0.55}
    assert possible_resolver_mismatch(skills_row, resolved_row) is True


def test_resolver_mismatch_ignores_small_gap():
    skills_row = {"f1": 0.50}
    resolved_row = {"f1": 0.55}
    assert possible_resolver_mismatch(skills_row, resolved_row) is False


def test_resolver_mismatch_false_when_no_sibling():
    skills_row = {"f1": 0.20}
    assert possible_resolver_mismatch(skills_row, None) is False


def test_compute_failure_signals_falls_back_to_unclear():
    row = {
        "tp_count": 10, "fp_count": 0, "fn_count": 0,
        "f1": 1.0, "field": "location",
    }
    assert compute_failure_signals(row) == ["unclear"]


def test_compute_failure_signals_zero_tp_and_fn_heavy():
    row = {
        "tp_count": 0, "fp_count": 1, "fn_count": 6,
        "f1": 0.0, "field": "skills",
    }
    signals = compute_failure_signals(row)
    assert "zero_tp_with_fn" in signals
    assert "fn_heavy" in signals


def test_compute_failure_signals_resolver_mismatch():
    skills_row = {
        "tp_count": 2, "fp_count": 3, "fn_count": 3,
        "f1": 0.20, "field": "skills",
    }
    resolved_row = {
        "tp_count": 5, "fp_count": 0, "fn_count": 0,
        "f1": 0.55, "field": "skills_resolved",
    }
    signals = compute_failure_signals(skills_row, sibling_row=resolved_row)
    assert "possible_resolver_canonicalization_mismatch" in signals

def test_is_fp_heavy_false_when_equal():
    row = {"fp_count": 3, "fn_count": 3}
    assert is_fp_heavy(row) is False


def test_is_high_total_error_uses_default_threshold():
    row = {"fp_count": 3, "fn_count": 3}  # total = 6, default threshold = 5
    assert is_high_total_error(row) is True


def test_is_low_f1_uses_default_threshold():
    row = {"tp_count": 1, "fp_count": 1, "fn_count": 1, "f1": 0.25}  # default threshold = 0.3
    assert is_low_f1(row) is True


def test_compute_failure_signals_includes_high_total_error():
    row = {
        "tp_count": 1, "fp_count": 3, "fn_count": 3,
        "f1": 0.15, "field": "location",
    }
    signals = compute_failure_signals(row)
    assert "high_total_error" in signals
    assert "low_f1" in signals