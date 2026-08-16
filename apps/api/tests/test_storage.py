import zipfile
from pathlib import Path

import pytest

from app.services.storage import StorageService, UnsafeUploadError


def storage(tmp_path: Path) -> StorageService:
    return StorageService(
        tmp_path / "storage",
        max_upload_bytes=1024,
        max_archive_entries=10,
        max_archive_uncompressed_bytes=4096,
    )


@pytest.mark.parametrize("member", ["../escape.html", "/absolute.html", "C:/drive.html"])
def test_rejects_zip_path_traversal(tmp_path, member: str) -> None:
    archive = tmp_path / "report.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(member, "<html></html>")

    with pytest.raises(UnsafeUploadError, match="Unsafe ZIP path"):
        storage(tmp_path).prepare_report_source("report-1", archive)


def test_extracts_relative_report_and_image(tmp_path) -> None:
    archive = tmp_path / "report.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("report/report.html", "<html></html>")
        output.writestr("report/images/clash.jpg", b"\xff\xd8\xfftest")

    source_root, html_path = storage(tmp_path).prepare_report_source("report-1", archive)

    assert html_path == source_root / "report" / "report.html"
    assert (source_root / "report" / "images" / "clash.jpg").is_file()
