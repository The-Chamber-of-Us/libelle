from services import parser_service


def test_parse_and_update_passes_submission_id_and_parsed_to_writeback(monkeypatch):
    """Regression for #153: update_resume_in_sheet must receive (submission_id, parsed)."""
    fake_parsed = {"skills": {"value": ["python"]}, "parser_version": "test"}
    captured = {}

    def fake_parse_resume(text):
        return dict(fake_parsed)

    def fake_update(submission_id, parsed):
        captured["submission_id"] = submission_id
        captured["parsed"] = parsed

    monkeypatch.setattr(parser_service, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(parser_service, "update_resume_in_sheet", fake_update)
    monkeypatch.setattr(parser_service, "_add_resolver_output", lambda parsed, submission_id: None)

    parser_service.parse_and_update(
        submission_id="sub-abc",
        drive_file_id="drive-xyz",
        pre_extracted_text="resume text",
    )

    assert captured["submission_id"] == "sub-abc"
    assert captured["parsed"]["skills"] == {"value": ["python"]}
    assert captured["parsed"]["drive_file_id"] == "drive-xyz"


def test_parse_and_update_stamps_submission_id_onto_parsed_payload(monkeypatch):
    """#126: the parser context must stamp submission_id onto the parsed payload
    so the parser's output is reliably linked back to the original submission."""
    captured = {}

    def fake_parse_resume(text):
        return {"skills": {"value": ["python"]}}

    def fake_update(submission_id, parsed):
        captured["parsed"] = parsed

    monkeypatch.setattr(parser_service, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(parser_service, "update_resume_in_sheet", fake_update)
    monkeypatch.setattr(parser_service, "_add_resolver_output", lambda parsed, submission_id: None)

    parser_service.parse_and_update(
        submission_id="sub-xyz-canonical",
        drive_file_id="drive-1",
        pre_extracted_text="resume text",
    )

    assert captured["parsed"]["submission_id"] == "sub-xyz-canonical"


def test_parse_and_update_adds_resolver_fields_without_replacing_raw_skills(monkeypatch):
    captured = {}

    def fake_parse_resume(text):
        return {
            "skills": {"value": ["React.js", "Python 3", "SomeUnknownThing"]},
            "locations": {"value": ["Raleigh, NC"]},
        }

    def fake_update(submission_id, parsed):
        captured["submission_id"] = submission_id
        captured["parsed"] = parsed

    monkeypatch.setattr(parser_service, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(
        parser_service,
        "_load_alias_map",
        lambda: ({"react.js": "react", "python3": "python"}, "aliases-test"),
    )
    monkeypatch.setattr(parser_service, "update_resume_in_sheet", fake_update)

    parser_service.parse_and_update(
        submission_id="sub-resolver",
        drive_file_id="drive-resolver",
        pre_extracted_text="resume text",
    )

    parsed = captured["parsed"]
    assert captured["submission_id"] == "sub-resolver"
    assert parsed["skills"]["value"] == ["React.js", "Python 3", "SomeUnknownThing"]
    assert parsed["resolver_version"] == "v1"
    assert parsed["aliases_version"] == "aliases-test"
    assert parsed["resolved_skill_ids"] == ["react", "python"]
    assert parsed["unknown_skills"] == ["SomeUnknownThing"]
    assert parsed["resolver_coverage"] == 0.667


def test_parse_and_update_writes_parser_output_when_resolver_fails(monkeypatch):
    captured = {}

    def fake_parse_resume(text):
        return {"skills": {"value": ["React.js"]}}

    def fake_resolver(parsed, submission_id):
        raise RuntimeError("resolver blew up")

    def fake_update(submission_id, parsed):
        captured["submission_id"] = submission_id
        captured["parsed"] = parsed

    monkeypatch.setattr(parser_service, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(parser_service, "_add_resolver_output", fake_resolver)
    monkeypatch.setattr(parser_service, "update_resume_in_sheet", fake_update)
    monkeypatch.setattr(parser_service, "append_error_row", lambda **kwargs: None)

    parser_service.parse_and_update(
        submission_id="sub-resolver-failure",
        drive_file_id="drive-resolver-failure",
        pre_extracted_text="resume text",
    )

    assert captured["submission_id"] == "sub-resolver-failure"
    assert captured["parsed"]["skills"] == {"value": ["React.js"]}
    assert captured["parsed"]["submission_id"] == "sub-resolver-failure"
    assert captured["parsed"]["drive_file_id"] == "drive-resolver-failure"
    assert "resolved_skill_ids" not in captured["parsed"]


def test_parse_and_update_swallows_exceptions(monkeypatch):
    """Background task must not propagate exceptions — callers rely on fire-and-forget."""
    logged = []

    def fake_parse_resume(text):
        raise RuntimeError("parser blew up")

    def fake_append_error_row(**kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(parser_service, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(parser_service, "append_error_row", fake_append_error_row)

    parser_service.parse_and_update(
        submission_id="sub-abc",
        drive_file_id="drive-xyz",
        pre_extracted_text="",
    )

    assert logged[0]["submission_id"] == "sub-abc"
    assert logged[0]["stage"] == "parser"
    assert logged[0]["error_code"] == "PARSER_FAILED"
    assert logged[0]["error_summary"] == "Parser failed"
    assert "parser blew up" in logged[0]["error_details"]


def test_parse_and_update_logs_resolver_failure_and_preserves_parser_output(monkeypatch):
    captured = {}
    logged = []

    def fake_parse_resume(text):
        return {
            "skills": {"value": ["python"]},
            "locations": {"value": ["Raleigh, NC"]},
        }

    def fake_resolver(parsed, submission_id):
        raise RuntimeError("resolver blew up")

    def fake_update(submission_id, parsed):
        captured["submission_id"] = submission_id
        captured["parsed"] = parsed

    def fake_append_error_row(**kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(parser_service, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(parser_service, "_add_resolver_output", fake_resolver)
    monkeypatch.setattr(parser_service, "update_resume_in_sheet", fake_update)
    monkeypatch.setattr(parser_service, "append_error_row", fake_append_error_row)

    parser_service.parse_and_update(
        submission_id="sub-resolver-fails",
        drive_file_id="drive-xyz",
        pre_extracted_text="resume text",
    )

    assert captured["submission_id"] == "sub-resolver-fails"
    assert captured["parsed"]["skills"] == {"value": ["python"]}
    assert captured["parsed"]["locations"] == {"value": ["Raleigh, NC"]}
    assert captured["parsed"]["submission_id"] == "sub-resolver-fails"
    assert logged[0]["submission_id"] == "sub-resolver-fails"
    assert logged[0]["stage"] == "resolver"
    assert logged[0]["error_code"] == "RESOLVER_FAILED"
    assert logged[0]["error_summary"] == "Resolver failed"
    assert "resolver blew up" in logged[0]["error_details"]


def test_parse_and_update_treats_zero_resolver_matches_as_success(monkeypatch):
    captured = {}
    logged = []

    def fake_parse_resume(text):
        return {
            "skills": {"value": ["unknown framework"]},
            "locations": {"value": []},
            "name": {"confidence": 0.0},
            "emails": {"confidence": 0.0},
        }

    def fake_update(submission_id, parsed):
        captured["parsed"] = parsed

    def fake_append_error_row(**kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(parser_service, "parse_resume", fake_parse_resume)
    monkeypatch.setattr(parser_service, "_load_alias_map", lambda: ({}, "aliases-test"))
    monkeypatch.setattr(parser_service, "update_resume_in_sheet", fake_update)
    monkeypatch.setattr(parser_service, "append_error_row", fake_append_error_row)

    parser_service.parse_and_update(
        submission_id="sub-zero",
        drive_file_id="drive-xyz",
        pre_extracted_text="resume text",
    )

    assert logged == []
    assert captured["parsed"]["resolver_version"] == parser_service.RESOLVER_VERSION
    assert captured["parsed"]["aliases_version"] == "aliases-test"
    assert captured["parsed"]["resolved_skill_ids"] == []
    assert captured["parsed"]["unknown_skills"] == ["unknown framework"]
    assert captured["parsed"]["resolver_coverage"] == 0.0
