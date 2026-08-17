from datetime import UTC, datetime

import pytest
from pypdf import PdfReader

from app.db.models import ClashItem, UploadedReport
from app.services.report_renderer import PdfUnavailableError, ReportRenderer
from app.services.storage import StorageService


def test_pdf_contains_report_and_clash_text(tmp_path) -> None:
    storage = StorageService(
        tmp_path / "storage",
        max_upload_bytes=1024,
        max_archive_entries=10,
        max_archive_uncompressed_bytes=4096,
    )
    report = UploadedReport(
        id="report-1",
        original_filename="coordination.html",
        title="Coordination Report",
        parser_version="navisworks-v1",
        errors=[],
        created_at=datetime.now(UTC),
    )
    clash = ClashItem(
        id="clash-1",
        report_id=report.id,
        clash_id="CD-001",
        row_index=1,
        grid="D-6",
        distance_raw="-62 mm",
        elements=[{"element_id": "123", "layer": "Level 2"}],
        source_metadata={},
    )
    try:
        pdf = ReportRenderer(storage).render(
            report=report,
            clashes=[clash],
            results={
                clash.id: {
                    "clash": True,
                    "clash_type": "Intersected",
                    "orientation": "Horizontal",
                    "cross_sectional_shape": "Circular",
                    "cross_sectional_size": "Small",
                    "severity": "Medium",
                    "recommended_action": "Review design priority.",
                }
            },
            model_version="Qwen2.5-VL-7B + adapter",
        )
    except PdfUnavailableError:
        pytest.skip("WeasyPrint native libraries are unavailable")

    path = tmp_path / "report.pdf"
    path.write_bytes(pdf)
    text = "".join(page.extract_text() or "" for page in PdfReader(path).pages)
    assert "Coordination Report" in text
    assert "CD-001" in text
    assert "Review design priority" in text
