from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_ingestion,
    get_renderer,
    get_session,
    get_settings,
    get_storage,
)
from app.core.config import Settings
from app.db.models import AnalysisResult, Artifact, Attachment, InferenceRun, UploadedReport
from app.domain.enums import ArtifactStatus, ParseStatus, RunStatus
from app.repositories.reports import ReportRepository
from app.schemas.api import ArtifactRead, AttachmentRead, ClashRead, ReportCreate, ReportRead
from app.services.report_ingestion import ReportIngestionService
from app.services.report_renderer import PdfUnavailableError, ReportRenderer
from app.services.storage import StorageService, UnsafeUploadError

router = APIRouter(tags=["reports"])


@router.post("/uploads", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> AttachmentRead:
    try:
        stored = await storage.save_upload(file)
    except UnsafeUploadError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    attachment = Attachment(
        original_filename=stored.original_filename,
        media_type=stored.media_type,
        storage_path=stored.storage_path,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
    )
    session.add(attachment)
    session.commit()
    return AttachmentRead.model_validate(attachment)


@router.post("/reports", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
    ingestion: ReportIngestionService = Depends(get_ingestion),
    settings: Settings = Depends(get_settings),
) -> ReportRead:
    repository = ReportRepository(session)
    source = repository.get_attachment(payload.upload_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    if source.media_type not in {"text/html", "application/zip"}:
        raise HTTPException(status_code=400, detail="Report source must be HTML or ZIP")
    if source.report_id is not None:
        raise HTTPException(status_code=409, detail="Upload is already assigned to a report")

    report = UploadedReport(
        original_filename=source.original_filename,
        title=(payload.title or Path(source.original_filename).stem).strip(),
        parse_status=ParseStatus.PENDING,
        parser_version=settings.parser_version,
        errors=[],
    )
    session.add(report)
    session.flush()
    source.report = report
    source.purpose = "source"
    session.commit()
    try:
        ingestion.ingest(session, report, storage.absolute(source.storage_path))
        session.commit()
    except (UnsafeUploadError, ValueError) as error:
        session.rollback()
        failed_report = session.get(UploadedReport, report.id)
        if failed_report is not None:
            failed_report.parse_status = ParseStatus.FAILED
            failed_report.errors = [{"row_index": 0, "message": str(error)}]
            session.commit()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _report_read(report, repository.count_clashes(report.id))


@router.get("/reports/{report_id}", response_model=ReportRead)
def get_report(report_id: str, session: Session = Depends(get_session)) -> ReportRead:
    repository = ReportRepository(session)
    report = repository.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_read(report, repository.count_clashes(report_id))


@router.get("/reports/{report_id}/clashes", response_model=list[ClashRead])
def list_clashes(report_id: str, session: Session = Depends(get_session)) -> list[ClashRead]:
    repository = ReportRepository(session)
    if repository.get(report_id) is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return [ClashRead.model_validate(item) for item in repository.list_clashes(report_id)]


@router.get("/clashes/{clash_item_id}/image", response_class=FileResponse)
def get_clash_image(
    clash_item_id: str,
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> FileResponse:
    clash = ReportRepository(session).get_clash(clash_item_id)
    if clash is None or not clash.image_path:
        raise HTTPException(status_code=404, detail="Clash image not found")
    path = storage.absolute(clash.image_path)
    return FileResponse(path, filename=path.name)


@router.post(
    "/reports/{report_id}/pdf", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED
)
def create_pdf(
    report_id: str,
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
    renderer: ReportRenderer = Depends(get_renderer),
    settings: Settings = Depends(get_settings),
) -> ArtifactRead:
    repository = ReportRepository(session)
    report = repository.get(report_id, with_clashes=True)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    artifact = Artifact(report_id=report.id, status=ArtifactStatus.PENDING)
    session.add(artifact)
    session.flush()

    completed = session.execute(
        select(AnalysisResult, InferenceRun)
        .join(InferenceRun, AnalysisResult.inference_run_id == InferenceRun.id)
        .where(
            InferenceRun.clash_item_id.in_([clash.id for clash in report.clashes]),
            InferenceRun.status == RunStatus.COMPLETED,
        )
        .order_by(InferenceRun.completed_at.desc())
    ).all()
    results: dict[str, dict[str, object]] = {}
    for result, run in completed:
        if run.clash_item_id:
            results.setdefault(run.clash_item_id, result.normalized)
    try:
        pdf = renderer.render(
            report=report,
            clashes=report.clashes,
            results=results,
            model_version=f"{settings.model_name} + {settings.adapter_name}",
        )
        artifact.storage_path = storage.write_artifact(artifact.id, pdf)
        artifact.size_bytes = len(pdf)
        artifact.status = ArtifactStatus.COMPLETED
        session.commit()
    except (PdfUnavailableError, OSError, ValueError) as error:
        artifact.status = ArtifactStatus.FAILED
        artifact.error = str(error)[:4_000]
        session.commit()
        raise HTTPException(status_code=503, detail=str(error)) from error
    return ArtifactRead.model_validate(artifact)


@router.get("/artifacts/{artifact_id}/download", response_class=FileResponse)
def download_artifact(
    artifact_id: str,
    session: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> FileResponse:
    artifact = ReportRepository(session).get_artifact(artifact_id)
    if artifact is None or artifact.status != ArtifactStatus.COMPLETED or not artifact.storage_path:
        raise HTTPException(status_code=404, detail="Completed artifact not found")
    return FileResponse(
        storage.absolute(artifact.storage_path),
        media_type=artifact.media_type,
        filename=f"clash-report-{artifact.report_id}.pdf",
    )


def _report_read(report: UploadedReport, clash_count: int) -> ReportRead:
    source = next(
        (attachment for attachment in report.attachments if attachment.purpose == "source"), None
    )
    if source is None:
        raise ValueError("Report has no source attachment")
    return ReportRead(
        id=report.id,
        source_attachment_id=source.id,
        original_filename=report.original_filename,
        title=report.title,
        parse_status=report.parse_status,
        parser_version=report.parser_version,
        errors=report.errors,
        clash_count=clash_count,
        created_at=report.created_at,
    )
