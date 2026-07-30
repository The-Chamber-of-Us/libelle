"""Evaluate valid V2 fixtures only on fields the current parser supports.

The V2 annotation contract, including the canonical representation of
``sections[]``, is defined in ``backend/benchmarks/v2_annotation_spec.md``.
This evaluator treats validation as the eligibility gate, then scores only
parser-comparable top-level fields. V2 structural fields are reported as not
evaluated until the parser emits a compatible structure.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    dedupe_normalized,
    load_json,
    normalize_for_exact,
    relative_fixture_map,
)
from .validate_v2_goldens import discover_and_validate


UNSUPPORTED_FIELDS = [
    "name",
    "email",
    "links",
    "sections",
    "section_heading_presence",
    "section_precision_recall_f1",
    "entry_counts_by_section",
    "structured_field_presence",
    "title_matching",
    "meta_matching",
    "subtitle_matching",
    "bullet_text",
    "bullet_order",
    "semantic_section_equivalence",
    "education_structure",
    "work_experience_structure",
    "project_experience_structure",
]


def _prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def _metric_not_evaluated(reason: str) -> Dict[str, Any]:
    return {"status": "not evaluated", "reason": reason}


def _field_value(predicted: Dict[str, Any], field: str, default: Any) -> Any:
    value = predicted.get(field, default)
    if isinstance(value, dict) and "value" in value:
        return value.get("value", default)
    return value


def _prediction_skills(predicted: Dict[str, Any]) -> List[str]:
    value = _field_value(predicted, "skills", [])
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def _prediction_location(predicted: Dict[str, Any]) -> Dict[str, str]:
    location = predicted.get("location")
    if isinstance(location, dict):
        return {
            "city": str(location.get("city") or ""),
            "country": str(location.get("country") or ""),
            "raw": str(location.get("raw") or ""),
        }

    locations = _field_value(predicted, "locations", [])
    if isinstance(locations, list) and locations:
        return {"city": "", "country": "", "raw": str(locations[0])}
    if isinstance(locations, str):
        return {"city": "", "country": "", "raw": locations}
    return {"city": "", "country": "", "raw": ""}


def _prediction_phones(predicted: Dict[str, Any]) -> List[str]:
    value = _field_value(predicted, "phones", [])
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def _phone_digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _set_metric(predicted_values: List[Any], golden_values: List[Any]) -> Dict[str, Any]:
    pred_set = set(dedupe_normalized(predicted_values))
    gold_set = set(dedupe_normalized(golden_values))
    tp_values = sorted(pred_set & gold_set)
    fp_values = sorted(pred_set - gold_set)
    fn_values = sorted(gold_set - pred_set)
    return {
        "status": "evaluated",
        "tp": len(tp_values),
        "fp": len(fp_values),
        "fn": len(fn_values),
        **_prf(len(tp_values), len(fp_values), len(fn_values)),
        "tp_examples": tp_values[:10],
        "fp_examples": fp_values[:10],
        "fn_examples": fn_values[:10],
    }


def _location_metric(golden: Dict[str, Any], predicted: Dict[str, Any]) -> Dict[str, Any]:
    gold_location = golden.get("location") if isinstance(golden.get("location"), dict) else {}
    pred_location = _prediction_location(predicted)
    components = {}
    tp = fp = fn = 0

    for component in ("country", "city", "raw"):
        gold_value = normalize_for_exact(gold_location.get(component))
        pred_value = normalize_for_exact(pred_location.get(component))
        if gold_value and pred_value == gold_value:
            status = "match"
            tp += 1
        elif gold_value and pred_value:
            status = "mismatch"
            fp += 1
            fn += 1
        elif gold_value:
            status = "missing"
            fn += 1
        elif pred_value:
            status = "extra"
            fp += 1
        else:
            status = "not present"
        components[component] = {
            "status": status,
            "expected": gold_location.get(component) or "",
            "observed": pred_location.get(component) or "",
        }

    return {
        "status": "evaluated",
        "tp": tp,
        "fp": fp,
        "fn": fn,
        **_prf(tp, fp, fn),
        "components": components,
    }


def _phone_metric(golden: Dict[str, Any], predicted: Dict[str, Any]) -> Dict[str, Any]:
    gold_phone = _phone_digits(golden.get("phone"))
    pred_phones = [_phone_digits(phone) for phone in _prediction_phones(predicted)]
    pred_phones = [phone for phone in pred_phones if phone]
    return _set_metric(pred_phones, [gold_phone] if gold_phone else [])


def score_current_parser_fields(golden: Dict[str, Any], predicted: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not predicted:
        reason = "no current-parser prediction supplied"
        return {
            "skills": _metric_not_evaluated(reason),
            "location": _metric_not_evaluated(reason),
            "phone": _metric_not_evaluated(reason),
        }

    return {
        "skills": _set_metric(_prediction_skills(predicted), golden.get("skills") or []),
        "location": _location_metric(golden, predicted),
        "phone": _phone_metric(golden, predicted),
    }


def evaluate(
    *,
    pdf_dir: Path,
    golden_dir: Path,
    prediction_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    validation_records = discover_and_validate(pdf_dir, golden_dir)
    prediction_map = relative_fixture_map(prediction_dir, ".json") if prediction_dir else {}
    fixtures = []

    for record in validation_records:
        if record.schema_version != "v2":
            fixtures.append(
                {
                    "fixture_id": record.fixture_id,
                    "schema_version": record.schema_version,
                    "validation_status": "skipped",
                    "evaluated_metric_names": [],
                    "metric_values": {},
                    "unsupported_fields": ["sections"],
                    "failure_count": len([i for i in record.issues if i.severity == "error"]),
                }
            )
            continue

        errors = [issue for issue in record.issues if issue.severity == "error"]
        if errors:
            fixtures.append(
                {
                    "fixture_id": record.fixture_id,
                    "schema_version": "v2",
                    "validation_status": "invalid",
                    "eligible_for_evaluation": False,
                    "evaluated_metric_names": [],
                    "metric_values": {},
                    "unsupported_fields": list(UNSUPPORTED_FIELDS),
                    "failure_count": len(errors),
                    "ineligible_reason": "fixture failed V2 validation",
                }
            )
            continue

        prediction = None
        prediction_error = None
        if prediction_dir and record.golden_path:
            key = record.golden_path.relative_to(golden_dir).with_suffix("").as_posix()
            pred_path = prediction_map.get(key) or prediction_map.get(Path(key).name)
            if pred_path:
                prediction, prediction_error = load_json(pred_path)

        metrics = score_current_parser_fields(record.golden or {}, prediction)
        if prediction_error:
            reason = f"prediction JSON could not be loaded: {prediction_error}"
            metrics = {name: _metric_not_evaluated(reason) for name in metrics}

        fixtures.append(
            {
                "fixture_id": record.fixture_id,
                "schema_version": "v2",
                "validation_status": "valid",
                "eligible_for_evaluation": True,
                "evaluated_metric_names": [
                    name for name, metric in metrics.items() if metric.get("status") == "evaluated"
                ],
                "metric_values": metrics,
                "unsupported_fields": list(UNSUPPORTED_FIELDS),
                "failure_count": 0,
            }
        )

    return {"fixtures": fixtures}


def _print_diagnostics(summary: Dict[str, Any]) -> None:
    for fixture in summary["fixtures"]:
        print(f"Fixture: {fixture['fixture_id']}")
        print(f"Schema: {fixture['schema_version']} | Validation: {fixture['validation_status']}")
        if fixture.get("eligible_for_evaluation") is False:
            print(f"Not eligible for evaluation: {fixture.get('ineligible_reason', 'validation failed')}")
        for name, metric in fixture["metric_values"].items():
            if metric.get("status") == "not evaluated":
                print(f"Not evaluated: {name} ({metric.get('reason', 'not available')}).")
        for field in fixture.get("unsupported_fields", []):
            if field.startswith(("section", "title", "meta", "subtitle", "bullet")):
                print(f"Unsupported comparison: {field} is not evaluated in this version.")
        print()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", required=True, type=Path)
    parser.add_argument("--golden-dir", required=True, type=Path)
    parser.add_argument("--prediction-dir", type=Path)
    parser.add_argument("--summary-out", type=Path)
    args = parser.parse_args(argv)

    summary = evaluate(pdf_dir=args.pdf_dir, golden_dir=args.golden_dir, prediction_dir=args.prediction_dir)
    _print_diagnostics(summary)
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_out.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
