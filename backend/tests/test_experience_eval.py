import pytest

from benchmarks.experience_eval import (
    extract_expected_experience_entries, extract_predicted_experience_entries,
    compare_experience_entries, rough_text_overlap, section_type,
)
from parser import parse_resume, extract_project_experience


def test_expected_preserves_multiple_sections_and_string_items():
    entries = extract_expected_experience_entries({"sections": [
        {"heading": "PROJECTS", "items": [{"title": "Planner", "meta": "2026", "subtitle": None, "bullets": ["Built app"]}]},
        {"heading": " Additional  Projects: ", "items": ["Other project"]},
        {"heading": "EDUCATION", "items": ["Degree"]},
    ]})
    assert len(entries) == 2
    assert entries[0]["raw_text"] == "Planner\n2026\nBuilt app"
    assert entries[1]["title"] is None
    assert section_type("employment history") == "work"
    assert section_type("LEADERSHIP & SERVICE") == "unknown"


def test_missing_annotation_and_malformed_prediction_do_not_become_zero():
    with pytest.raises(ValueError):
        extract_expected_experience_entries({})
    with pytest.raises(ValueError):
        extract_predicted_experience_entries({"work_experience": {"value": "bad shape"}})


def test_raw_predictions_preserve_text_without_invented_fields():
    entries = extract_predicted_experience_entries({"work_experience": {"value": ["Engineer 2026 Built API"], "confidence": 1}})
    assert entries[0]["raw_text"] == "Engineer 2026 Built API"
    assert entries[0]["title"] is None
    assert entries[0]["source_section"] is None
    assert entries[0]["bullets"] == []


def test_fragment_coverage_does_not_imply_entry_match():
    expected = extract_expected_experience_entries({"sections": [{"heading": "PROJECTS", "items": ["alpha beta gamma delta"]}]})
    predicted = extract_predicted_experience_entries({"project_experience": ["alpha beta", "gamma delta"]})
    result = compare_experience_entries(expected, predicted)
    assert result["best_project_overlap"] == 0.5
    assert result["entry_diagnostics"][0]["raw_token_coverage_across_fragments"] == 1
    assert result["predicted_project_count"] == 2
    assert rough_text_overlap({"raw_text": ""}, {"raw_text": ""}) == 0


def test_project_order_counterfactual_uses_real_parser():
    text = "PROJECTS\nPlanner 2026\nBuilt web app\nEXPERIENCE\nEngineer 2025\nBuilt API\nSKILLS\nPython"
    parsed = parse_resume(text)
    assert parsed["project_experience"]["value"] == []
    assert extract_project_experience(text, 0)[0] == ["Planner 2026 Built web app"]


def test_type_confusion_is_diagnostic_only():
    expected = extract_expected_experience_entries({"sections": [{"heading": "PROJECTS", "items": ["Built course planner web application"]}]})
    predicted = extract_predicted_experience_entries({"work_experience": ["Built course planner web application"]})
    result = compare_experience_entries(expected, predicted)
    assert "possible work/project confusion" in result["notes"]
    assert result["best_project_overlap"] == 0
    assert result["predicted_project_count"] == 0


def test_report_runs_real_public_v2_pipeline(tmp_path):
    import importlib.util
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("benchmark_experience", root / "scripts/benchmark_experience.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    summary = runner.run(root / "backend/benchmarks/resumes/v2", root / "backend/benchmarks/golden_json/v2", tmp_path)
    assert summary["sample_size"] == 10
    assert summary["exploratory"] is True
    traces = json.loads((tmp_path / "experience_traces.json").read_text())
    first = next(t for t in traces if t["resume"] == "resume_201")
    assert first["parsed"]["project_experience"]["value"] == []
    assert first["projects_start_zero"]
    assert "ADDITIONAL PROJECTS" in {e["source_section"] for e in first["expected"]}
    assert len(first["input_sha256"]["pdf"]) == 64
    assert (tmp_path / "experience_report.csv").is_file()
