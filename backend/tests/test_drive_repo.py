from storage import drive_repo


def test_build_deterministic_resume_filename_preserves_original_extension_safely():
    assert (
        drive_repo.build_deterministic_resume_filename(
            "sub_123",
            "../My Resume.PDF",
        )
        == "sub_123_My Resume.PDF"
    )


def test_upload_pdf_sends_deterministic_filename_to_drive(monkeypatch):
    captured = {}

    class FakeCreate:
        def execute(self):
            return {"id": "drive-file-id", "webViewLink": "https://drive.example/view"}

    class FakeFiles:
        def create(self, *, body, media_body, fields):
            captured["body"] = body
            captured["fields"] = fields
            captured["media_body"] = media_body
            return FakeCreate()

    class FakeDriveService:
        def files(self):
            return FakeFiles()

    monkeypatch.setattr(drive_repo, "get_drive_service", lambda: FakeDriveService())

    file_id, web_view, filename = drive_repo.upload_pdf(
        b"%PDF-1.4 stub",
        "sub_123",
        "Original Resume.pdf",
        parent_folder_id="folder-123",
    )

    assert file_id == "drive-file-id"
    assert web_view == "https://drive.example/view"
    assert filename == "sub_123_Original Resume.pdf"
    assert captured["body"]["name"] == filename
    assert captured["body"]["parents"] == ["folder-123"]
