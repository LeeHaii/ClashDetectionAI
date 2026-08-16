from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Artifact, Attachment, ClashItem, UploadedReport


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_attachment(self, attachment_id: str) -> Attachment | None:
        return self.session.get(Attachment, attachment_id)

    def get(self, report_id: str, *, with_clashes: bool = False) -> UploadedReport | None:
        statement = select(UploadedReport).where(UploadedReport.id == report_id)
        if with_clashes:
            statement = statement.options(selectinload(UploadedReport.clashes))
        return self.session.scalar(statement)

    def count_clashes(self, report_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count(ClashItem.id)).where(ClashItem.report_id == report_id)
            )
            or 0
        )

    def list_clashes(self, report_id: str) -> list[ClashItem]:
        return list(
            self.session.scalars(
                select(ClashItem)
                .where(ClashItem.report_id == report_id)
                .order_by(ClashItem.row_index)
            )
        )

    def get_clash(self, clash_item_id: str) -> ClashItem | None:
        return self.session.get(ClashItem, clash_item_id)

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        return self.session.get(Artifact, artifact_id)
