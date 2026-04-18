import pytest

import validator
from sheet_schema import SHEET_SCHEMA


def _matching_snapshot() -> dict:
    return {
        "tabs": list(SHEET_SCHEMA.keys()),
        "headers": {tab: list(headers) for tab, headers in SHEET_SCHEMA.items()},
    }


def _patch(monkeypatch, snapshot: dict) -> None:
    monkeypatch.setattr(validator, "fetch_live_schema", lambda: snapshot)


def test_validate_success_prints_schema_validated(monkeypatch, capsys):
    _patch(monkeypatch, _matching_snapshot())

    validator.validate_sheet_schema()

    assert "[SCHEMA] Schema Validated" in capsys.readouterr().out


def test_validate_header_mismatch_names_tab_and_diff(monkeypatch):
    snapshot = _matching_snapshot()
    snapshot["headers"]["submissions"] = [
        "email_address" if h == "email" else h for h in snapshot["headers"]["submissions"]
    ]
    _patch(monkeypatch, snapshot)

    with pytest.raises(validator.SchemaValidationError) as exc:
        validator.validate_sheet_schema()

    message = str(exc.value)
    assert "[submissions] Header mismatch." in message
    assert "'email'" in message
    assert "'email_address'" in message


def test_validate_missing_tab_named_explicitly(monkeypatch):
    snapshot = _matching_snapshot()
    snapshot["tabs"].remove("errors")
    snapshot["headers"].pop("errors", None)
    _patch(monkeypatch, snapshot)

    with pytest.raises(validator.SchemaValidationError) as exc:
        validator.validate_sheet_schema()

    message = str(exc.value)
    assert "missing tabs:" in message
    assert "'errors'" in message


def test_validate_empty_row_reports_all_headers_missing(monkeypatch):
    snapshot = _matching_snapshot()
    snapshot["headers"]["ops"] = []
    _patch(monkeypatch, snapshot)

    with pytest.raises(validator.SchemaValidationError) as exc:
        validator.validate_sheet_schema()

    message = str(exc.value)
    assert "[ops] Header mismatch." in message
    for expected_header in SHEET_SCHEMA["ops"]:
        assert f"'{expected_header}'" in message
