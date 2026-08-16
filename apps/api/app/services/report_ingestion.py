from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import ClashItem, UploadedReport
from app.domain.enums import ParseStatus
from app.schemas.analysis import ElementMetadata
from app.services.html_parser import HtmlParser
from app.services.storage import StorageService


class ReportIngestionService:
    def __init__(self, storage: StorageService, parser: HtmlParser) -> None:
        self.storage = storage
        self.parser = parser

    def ingest(self, session: Session, report: UploadedReport, source_path: Path) -> UploadedReport:
        source_root, html_path = self.storage.prepare_report_source(report.id, source_path)
        parsed = self.parser.parse(html_path, source_root)
        for clash in parsed.clashes:
            image_path: str | None = None
            if clash.embedded_image is not None and clash.embedded_media_type is not None:
                image_path = self.storage.write_report_image(
                    report.id, clash.clash_id, clash.embedded_image, clash.embedded_media_type
                )
            elif clash.image_reference:
                image_path = self.storage.relative(source_root / clash.image_reference)
            session.add(
                ClashItem(
                    report_id=report.id,
                    clash_id=clash.clash_id,
                    row_index=clash.row_index,
                    image_path=image_path,
                    distance_raw=clash.distance_raw,
                    distance_m=clash.distance_m,
                    grid=clash.grid,
                    clash_point=clash.clash_point,
                    elements=[self._element_dict(element) for element in clash.elements],
                    source_metadata=clash.source_metadata,
                )
            )
        report.errors = [error.model_dump() for error in parsed.errors]
        if parsed.clashes and parsed.errors:
            report.parse_status = ParseStatus.PARTIAL
        elif parsed.clashes:
            report.parse_status = ParseStatus.COMPLETED
        else:
            report.parse_status = ParseStatus.FAILED
        session.flush()
        return report

    @staticmethod
    def _element_dict(element: ElementMetadata) -> dict[str, object]:
        return element.model_dump()
