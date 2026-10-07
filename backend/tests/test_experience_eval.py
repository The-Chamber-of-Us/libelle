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
    entries = extract_predicted_experience_entries({"work_experience": {"value": ["Engineer 2026 Built API"], "confidence": 1}, "project_experience": []})
    assert entries[0]["raw_text"] == "Engineer 2026 Built API"
    assert entries[0]["title"] is None
    assert entries[0]["source_section"] is None
    assert entries[0]["bullets"] == []


def test_fragment_coverage_does_not_imply_entry_match():
    expected = extract_expected_experience_entries({"sections": [{"heading": "PROJECTS", "items": ["alpha beta gamma delta"]}]})
    predicted = extract_predicted_experience_entries({"work_experience": [], "project_experience": ["alpha beta", "gamma delta"]})
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
    predicted = extract_predicted_experience_entries({"work_experience": ["Built course planner web application"], "project_experience": []})
    result = compare_experience_entries(expected, predicted)
    assert "possible work/project confusion" in result["notes"]
    assert result["best_project_overlap"] == 0
    assert result["predicted_project_count"] == 0


@pytest.fixture
def runner():
    import importlib.util
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("benchmark_experience", root / "scripts/benchmark_experience.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


@pytest.fixture(scope="module")
def real_evaluation(tmp_path_factory):
    import importlib.util
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("benchmark_experience_real", root / "scripts/benchmark_experience.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path_factory.mktemp("experience")
    summary = module.run(root / "backend/benchmarks/resumes/v2", root / "backend/benchmarks/golden_json/v2", out)
    traces = json.loads((out / "experience_traces.json").read_text())
    return summary, {t["resume"]: t for t in traces}, out


def test_report_runs_real_public_v2_pipeline(real_evaluation):
    summary, traces, out = real_evaluation
    assert summary["sample_size"] == 10
    assert summary["exploratory"] is True
    first = traces["resume_201"]
    assert first["parsed"]["project_experience"]["value"] == []
    assert first["projects_start_zero"]
    assert "ADDITIONAL PROJECTS" in {e["source_section"] for e in first["expected"]}
    assert len(first["input_sha256"]["pdf"]) == 64
    assert (out / "experience_report.csv").is_file()


def test_corrected_corpus_accounting(real_evaluation):
    summary, traces, _ = real_evaluation
    assert summary["accounting"]["work"] == {
        "expected_entries": 19, "predicted_fragments": 55,
        "fixtures_with_expected": 10,
        "fixtures_with_missing_output": ["resume_204", "resume_206", "resume_208"],
    }
    assert summary["accounting"]["project"] == {
        "expected_entries": 19, "predicted_fragments": 20,
        "fixtures_with_expected": 7,
        "fixtures_with_missing_output": ["resume_201", "resume_203", "resume_205", "resume_206", "resume_207", "resume_210"],
    }
    for name, heading in [("resume_204", "Research Experience"), ("resume_206", "ENGINEERING EXPERIENCE"), ("resume_208", "PROFESSIONAL BACKGROUND")]:
        assert {e["source_section"] for e in traces[name]["expected"] if e["entry_type"] == "work"} == {heading}
        assert "work section missed" in traces[name]["comparison"]["notes"]
    assert {"heading": "SELECTED REPORTING WORK", "item_count": 2} in summary["unmapped_sections"]["resume_208"]
    assert {"heading": "Additional Campus Work", "item_count": 2} in summary["unmapped_sections"]["resume_209"]


def test_202_preserves_work_text_but_fragments_entries(real_evaluation):
    _, traces, _ = real_evaluation
    trace = traces["resume_202"]
    result = trace["comparison"]
    assert (result["expected_work_count"], result["predicted_work_count"]) == (3, 15)
    work = [d for d in result["entry_diagnostics"] if d["entry_type"] == "work"]
    assert len(work) == 3
    assert all(d["raw_token_coverage_across_fragments"] == 1 for d in work)
    assert all(d["field_token_coverage_across_fragments"] == {"title": 1, "meta": 1, "subtitle": 1} for d in work)
    assert all(all(c == 1 for c in d["bullet_token_coverage_across_fragments"]) for d in work)
    assert all(d["best_jaccard"] < 0.4 for d in work)
    assert all(e["title"] is None and not e["bullets"] for e in trace["predicted"])


def test_203_unsupported_project_heading_still_misses_at_zero(real_evaluation):
    _, traces, _ = real_evaluation
    trace = traces["resume_203"]
    projects = [e for e in trace["expected"] if e["entry_type"] == "project"]
    assert len(projects) == 2
    assert {e["source_section"] for e in projects} == {"TECHNICAL PROJECTS"}
    assert all(e["title"] in trace["extracted_text"] for e in projects)
    assert trace["parsed"]["project_experience"]["value"] == []
    assert trace["projects_start_zero"] == []


def test_205_work_end_probe_does_not_replace_predictions(real_evaluation):
    _, traces, _ = real_evaluation
    trace = traces["resume_205"]
    result = trace["comparison"]
    assert result["expected_project_count"] == 3
    assert result["predicted_project_count"] == 0
    assert result["work_end_index"] == 51
    assert len(trace["projects_start_zero"]) == 14
    assert trace["parsed"]["project_experience"]["value"] == []
    assert all(e["entry_type"] != "project" for e in trace["predicted"])


def test_209_project_output_bleeds_and_more_projects_is_accounted(real_evaluation):
    _, traces, _ = real_evaluation
    trace = traces["resume_209"]
    assert (trace["comparison"]["expected_project_count"], trace["comparison"]["predicted_project_count"]) == (2, 20)
    assert {e["title"] for e in trace["expected"] if e["entry_type"] == "project"} == {"Budget Splitter", "Subway Delay Notes"}
    project_text = "\n".join(e["raw_text"] for e in trace["predicted"] if e["entry_type"] == "project")
    for content in ["Python; SQL; Java; Excel", "Peer Mentor", "Computer Lab Monitor", "Data Structures; Discrete Mathematics"]:
        assert content in project_text
        assert content in trace["extracted_text"]
    assert "possible section bleed: Additional Campus Work, Coursework, SKILLS & INTERESTS" in trace["comparison"]["notes"]


@pytest.mark.parametrize("item", [{}, {"title": "", "meta": None, "subtitle": None, "bullets": []}, {"title": "Role"}, "   ", None])
def test_invalid_expected_items_fail_with_context(item):
    with pytest.raises(ValueError, match="sections|items"):
        extract_expected_experience_entries({"sections": [{"heading": "EXPERIENCE", "items": [item]}]})


@pytest.mark.parametrize("parsed, message", [
    ({}, "work_experience"),
    ({"work_experience": []}, "project_experience"),
    ({"project_experience": []}, "work_experience"),
    ({"work_experience": {}, "project_experience": []}, "missing value"),
    ({"work_experience": None, "project_experience": []}, "entry list"),
    ({"work_experience": [" "], "project_experience": []}, "non-empty"),
    ({"work_experience": [{}], "project_experience": []}, "structured entry field"),
])
def test_missing_or_malformed_predictions_are_not_extraction_misses(parsed, message):
    with pytest.raises(ValueError, match=message):
        extract_predicted_experience_entries(parsed)


def test_explicit_empty_prediction_lists_are_valid():
    assert extract_predicted_experience_entries({"work_experience": {"value": []}, "project_experience": []}) == []


@pytest.mark.parametrize("kind", ["empty", "unpaired", "malformed_json", "non_v2", "empty_item"])
def test_runner_rejects_invalid_inputs_before_writing_reports(runner, tmp_path, kind):
    import json
    from pathlib import Path

    pdfs, goldens, out = tmp_path / "pdfs", tmp_path / "goldens", tmp_path / "out"
    pdfs.mkdir()
    goldens.mkdir()
    if kind != "empty":
        (pdfs / "resume_201.pdf").write_bytes(b"not opened before validation")
    if kind == "malformed_json":
        (goldens / "resume_201.json").write_text("{")
    elif kind == "non_v2":
        (goldens / "resume_201.json").write_text("{}")
    elif kind == "empty_item":
        root = Path(__file__).resolve().parents[2]
        golden = json.loads((root / "backend/benchmarks/golden_json/v2/resume_201.json").read_text())
        golden["sections"][2]["items"][0] = {}
        (goldens / "resume_201.json").write_text(json.dumps(golden))
    with pytest.raises(ValueError, match="Invalid experience benchmark inputs"):
        runner.run(pdfs, goldens, out)
    assert not out.exists()


def test_runner_rejects_missing_prediction_field_with_fixture_context(runner, tmp_path, monkeypatch):
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(runner, "parse_resume", lambda text: {"work_experience": []})
    with pytest.raises(ValueError, match="resume_201.*missing required prediction field: project_experience"):
        runner.run(root / "backend/benchmarks/resumes/v2", root / "backend/benchmarks/golden_json/v2", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_cli_requires_explicit_output_directory(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, str(root / "scripts/benchmark_experience.py")], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2
    assert "required: --out" in result.stderr
    assert not list(tmp_path.iterdir())
