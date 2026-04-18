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

    parser_service.parse_and_update(
        submission_id="sub-abc",
        drive_file_id="drive-xyz",
        pre_extracted_text="resume text",
    )

    assert captured["submission_id"] == "sub-abc"
    assert captured["parsed"]["skills"] == {"value": ["python"]}
    assert captured["parsed"]["drive_file_id"] == "drive-xyz"


def test_parse_and_update_swallows_exceptions(monkeypatch):
    """Background task must not propagate exceptions — callers rely on fire-and-forget."""
    def fake_parse_resume(text):
        raise RuntimeError("parser blew up")

    monkeypatch.setattr(parser_service, "parse_resume", fake_parse_resume)

    parser_service.parse_and_update(
        submission_id="sub-abc",
        drive_file_id="drive-xyz",
        pre_extracted_text="",
    )
