import pytest

from services import parser_service


@pytest.fixture(autouse=True)
def durable_pdf(monkeypatch):
    monkeypatch.setattr(parser_service, "download_file", lambda _: b"durable pdf")


def test_parse_and_update_reconstructs_parser_input_from_drive(monkeypatch):
    captured = {}

    def fake_download(file_id):
        captured["downloaded"] = file_id
        return b"stored pdf"

    def fake_parse_resume_pdf(pdf_bytes):
        captured["parsed"] = pdf_bytes
        return {"skills": {"value": ["python"]}}

    monkeypatch.setattr(parser_service, "download_file", fake_download)
    monkeypatch.setattr(parser_service, "parse_resume_pdf", fake_parse_resume_pdf)
    monkeypatch.setattr(parser_service, "update_resume_in_sheet", lambda *_: None)
    monkeypatch.setattr(parser_service, "_add_resolver_output", lambda *_: None)

    parser_service.parse_and_update("sub-layout", "drive-layout")

    assert captured == {
        "downloaded": "drive-layout",
        "parsed": b"stored pdf",
    }


def test_parse_and_update_passes_submission_id_and_parsed_to_writeback(monkeypatch):
    """Regression for #153: writeback receives (submission_id, parsed)."""
    fake_parsed = {"skills": {"value": ["python"]}, "parser_version": "test"}
    captured = {}

    monkeypatch.setattr(
        parser_service, "parse_resume_pdf", lambda _: dict(fake_parsed)
    )
    monkeypatch.setattr(
        parser_service,
        "update_resume_in_sheet",
        lambda submission_id, parsed: captured.update(
            submission_id=submission_id, parsed=parsed
        ),
    )
    monkeypatch.setattr(parser_service, "_add_resolver_output", lambda *_: None)

    parser_service.parse_and_update("sub-abc", "drive-xyz")

    assert captured["submission_id"] == "sub-abc"
    assert captured["parsed"]["skills"] == {"value": ["python"]}
    assert captured["parsed"]["drive_file_id"] == "drive-xyz"


def test_parse_and_update_stamps_submission_id_onto_parsed_payload(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        parser_service,
        "parse_resume_pdf",
        lambda _: {"skills": {"value": ["python"]}},
    )
    monkeypatch.setattr(
        parser_service,
        "update_resume_in_sheet",
        lambda _, parsed: captured.setdefault("parsed", parsed),
    )
    monkeypatch.setattr(parser_service, "_add_resolver_output", lambda *_: None)

    parser_service.parse_and_update("sub-xyz-canonical", "drive-1")

    assert captured["parsed"]["submission_id"] == "sub-xyz-canonical"


def test_parse_and_update_adds_resolver_fields_without_replacing_raw_skills(
    monkeypatch,
):
    captured = {}
    monkeypatch.setattr(
        parser_service,
        "parse_resume_pdf",
        lambda _: {
            "skills": {"value": ["React.js", "Python 3", "SomeUnknownThing"]},
            "locations": {"value": ["Raleigh, NC"]},
        },
    )
    monkeypatch.setattr(
        parser_service,
        "_load_alias_map",
        lambda: ({"react.js": "react", "python3": "python"}, "aliases-test"),
    )
    monkeypatch.setattr(
        parser_service,
        "update_resume_in_sheet",
        lambda submission_id, parsed: captured.update(
            submission_id=submission_id, parsed=parsed
        ),
    )

    parser_service.parse_and_update("sub-resolver", "drive-resolver")

    parsed = captured["parsed"]
    assert parsed["skills"]["value"] == ["React.js", "Python 3", "SomeUnknownThing"]
    assert parsed["resolver_version"] == "v1"
    assert parsed["aliases_version"] == "aliases-test"
    assert parsed["resolved_skill_ids"] == ["react", "python"]
    assert parsed["unknown_skills"] == ["SomeUnknownThing"]
    assert parsed["resolver_coverage"] == 0.667


def test_parse_and_update_writes_parser_output_when_resolver_fails(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        parser_service,
        "parse_resume_pdf",
        lambda _: {"skills": {"value": ["React.js"]}},
    )
    monkeypatch.setattr(
        parser_service,
        "_add_resolver_output",
        lambda *_: (_ for _ in ()).throw(RuntimeError("resolver blew up")),
    )
    monkeypatch.setattr(
        parser_service,
        "update_resume_in_sheet",
        lambda submission_id, parsed: captured.update(
            submission_id=submission_id, parsed=parsed
        ),
    )
    monkeypatch.setattr(parser_service, "append_error_row", lambda **_: None)

    parser_service.parse_and_update("sub-resolver-failure", "drive-resolver-failure")

    assert captured["submission_id"] == "sub-resolver-failure"
    assert captured["parsed"]["skills"] == {"value": ["React.js"]}
    assert captured["parsed"]["submission_id"] == "sub-resolver-failure"
    assert captured["parsed"]["drive_file_id"] == "drive-resolver-failure"
    assert "resolved_skill_ids" not in captured["parsed"]


def test_parse_and_update_swallows_parser_exceptions(monkeypatch):
    logged = []
    monkeypatch.setattr(
        parser_service,
        "parse_resume_pdf",
        lambda _: (_ for _ in ()).throw(RuntimeError("parser blew up")),
    )
    monkeypatch.setattr(
        parser_service,
        "append_error_row",
        lambda **kwargs: logged.append(kwargs),
    )

    parser_service.parse_and_update("sub-abc", "drive-xyz")

    assert logged[0]["submission_id"] == "sub-abc"
    assert logged[0]["stage"] == "parser"
    assert logged[0]["error_code"] == "PARSER_FAILED"
    assert logged[0]["error_summary"] == "Parser failed"
    assert "parser blew up" in logged[0]["error_details"]


def test_parse_and_update_logs_resolver_failure_and_preserves_parser_output(
    monkeypatch,
):
    captured = {}
    logged = []
    monkeypatch.setattr(
        parser_service,
        "parse_resume_pdf",
        lambda _: {
            "skills": {"value": ["python"]},
            "locations": {"value": ["Raleigh, NC"]},
        },
    )
    monkeypatch.setattr(
        parser_service,
        "_add_resolver_output",
        lambda *_: (_ for _ in ()).throw(RuntimeError("resolver blew up")),
    )
    monkeypatch.setattr(
        parser_service,
        "update_resume_in_sheet",
        lambda submission_id, parsed: captured.update(
            submission_id=submission_id, parsed=parsed
        ),
    )
    monkeypatch.setattr(
        parser_service,
        "append_error_row",
        lambda **kwargs: logged.append(kwargs),
    )

    parser_service.parse_and_update("sub-resolver-fails", "drive-xyz")

    assert captured["parsed"]["skills"] == {"value": ["python"]}
    assert captured["parsed"]["locations"] == {"value": ["Raleigh, NC"]}
    assert captured["parsed"]["submission_id"] == "sub-resolver-fails"
    assert logged[0]["stage"] == "resolver"
    assert logged[0]["error_code"] == "RESOLVER_FAILED"
    assert "resolver blew up" in logged[0]["error_details"]


def test_parse_and_update_treats_zero_resolver_matches_as_success(monkeypatch):
    captured = {}
    logged = []
    monkeypatch.setattr(
        parser_service,
        "parse_resume_pdf",
        lambda _: {
            "skills": {"value": ["unknown framework"]},
            "locations": {"value": []},
            "name": {"confidence": 0.0},
            "emails": {"confidence": 0.0},
        },
    )
    monkeypatch.setattr(parser_service, "_load_alias_map", lambda: ({}, "aliases-test"))
    monkeypatch.setattr(
        parser_service,
        "update_resume_in_sheet",
        lambda _, parsed: captured.setdefault("parsed", parsed),
    )
    monkeypatch.setattr(
        parser_service,
        "append_error_row",
        lambda **kwargs: logged.append(kwargs),
    )

    parser_service.parse_and_update("sub-zero", "drive-xyz")

    assert logged == []
    assert captured["parsed"]["resolver_version"] == parser_service.RESOLVER_VERSION
    assert captured["parsed"]["aliases_version"] == "aliases-test"
    assert captured["parsed"]["resolved_skill_ids"] == []
    assert captured["parsed"]["unknown_skills"] == ["unknown framework"]
    assert captured["parsed"]["resolver_coverage"] == 0.0
