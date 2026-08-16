from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.events import RunEventBroker
from app.services.inference import InferenceService
from app.services.report_ingestion import ReportIngestionService
from app.services.report_renderer import ReportRenderer
from app.services.storage import StorageService


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> StorageService:
    return request.app.state.storage


def get_ingestion(request: Request) -> ReportIngestionService:
    return request.app.state.ingestion


def get_inference(request: Request) -> InferenceService:
    return request.app.state.inference


def get_broker(request: Request) -> RunEventBroker:
    return request.app.state.broker


def get_renderer(request: Request) -> ReportRenderer:
    return request.app.state.renderer
