from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_broker, get_inference, get_session, get_settings
from app.core.config import Settings
from app.db.models import ClashItem, Conversation, InferenceRun, Message
from app.domain.enums import RunStatus
from app.schemas.api import InferenceRunCreate, InferenceRunRead
from app.services.events import RunEventBroker
from app.services.inference import InferenceService

router = APIRouter(prefix="/inference-runs", tags=["inference"])


@router.post("", response_model=InferenceRunRead, status_code=status.HTTP_202_ACCEPTED)
async def create_inference_run(
    payload: InferenceRunCreate,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    inference: InferenceService = Depends(get_inference),
) -> InferenceRunRead:
    conversation = session.get(Conversation, payload.conversation_id)
    message = session.get(Message, payload.user_message_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if message is None or message.conversation_id != conversation.id or message.role != "user":
        raise HTTPException(
            status_code=400, detail="A user message from this conversation is required"
        )
    if payload.clash_item_id and session.get(ClashItem, payload.clash_item_id) is None:
        raise HTTPException(status_code=404, detail="Clash item not found")
    run = InferenceRun(
        conversation_id=conversation.id,
        clash_item_id=payload.clash_item_id,
        user_message_id=message.id,
        status=RunStatus.PENDING,
        model_name=settings.model_name,
        adapter_version=settings.adapter_name,
        prompt_version=settings.prompt_version,
    )
    session.add(run)
    session.commit()
    inference.start(run.id)
    return InferenceRunRead.model_validate(run)


@router.get("/{run_id}", response_model=InferenceRunRead)
def get_inference_run(run_id: str, session: Session = Depends(get_session)) -> InferenceRunRead:
    run = session.scalar(
        select(InferenceRun)
        .where(InferenceRun.id == run_id)
        .options(selectinload(InferenceRun.result))
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Inference run not found")
    return InferenceRunRead.model_validate(run)


@router.get("/{run_id}/events", response_class=EventSourceResponse)
async def stream_inference_run(
    run_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    session: Session = Depends(get_session),
    broker: RunEventBroker = Depends(get_broker),
) -> AsyncIterator[ServerSentEvent]:
    run = session.scalar(
        select(InferenceRun)
        .where(InferenceRun.id == run_id)
        .options(selectinload(InferenceRun.result))
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Inference run not found")
    try:
        cursor = int(last_event_id or 0)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Last-Event-ID must be an integer") from error

    if run.status in {RunStatus.COMPLETED, RunStatus.CANCELLED, RunStatus.FAILED} and cursor == 0:
        if run.status == RunStatus.COMPLETED and run.result is not None:
            yield ServerSentEvent(
                data={"result": run.result.normalized, "markdown": run.result.markdown},
                event="result.completed",
                id="1",
            )
        elif run.status == RunStatus.CANCELLED:
            yield ServerSentEvent(data={"run_id": run.id}, event="run.cancelled", id="1")
        else:
            yield ServerSentEvent(
                data={"message": run.error or "Inference failed"}, event="error", id="1"
            )
        yield ServerSentEvent(data={}, event="done", id="2")
        return

    async for event in broker.stream(run_id, cursor):
        if event.name == "ping":
            yield ServerSentEvent(comment="ping")
        else:
            yield ServerSentEvent(data=event.data, event=event.name, id=str(event.id))


@router.post("/{run_id}/cancel", response_model=InferenceRunRead)
def cancel_inference_run(
    run_id: str,
    session: Session = Depends(get_session),
    inference: InferenceService = Depends(get_inference),
) -> InferenceRunRead:
    run = session.get(InferenceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Inference run not found")
    if run.status in {RunStatus.COMPLETED, RunStatus.CANCELLED, RunStatus.FAILED}:
        return InferenceRunRead.model_validate(run)
    run.cancellation_requested = True
    session.commit()
    inference.interrupt(run_id)
    return InferenceRunRead.model_validate(run)
