from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_storage
from app.schemas.api import HealthRead
from app.services.storage import StorageService

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    return HealthRead(status="ok", checks={"process": True})


@router.get("/ready", response_model=HealthRead)
def ready(
    session: Session = Depends(get_session), storage: StorageService = Depends(get_storage)
) -> HealthRead:
    database_ok = False
    storage_ok = False
    try:
        session.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        database_ok = False
    try:
        storage_ok = Path(storage.root).is_dir()
    except OSError:
        storage_ok = False
    checks = {"database": database_ok, "storage": storage_ok}
    return HealthRead(status="ok" if all(checks.values()) else "not_ready", checks=checks)
