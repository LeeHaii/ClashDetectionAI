from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.db.models import Attachment
from app.repositories.conversations import ConversationRepository, MessageRepository
from app.schemas.api import (
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate, session: Session = Depends(get_session)
) -> ConversationRead:
    conversation = ConversationRepository(session).create(payload.title)
    session.commit()
    return ConversationRead.model_validate(conversation)


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    archived: bool = False,
    search: str | None = Query(default=None, max_length=200),
    session: Session = Depends(get_session),
) -> list[ConversationRead]:
    conversations = ConversationRepository(session).list(archived=archived, search=search)
    return [ConversationRead.model_validate(item) for item in conversations]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str, session: Session = Depends(get_session)
) -> ConversationDetail:
    conversation = ConversationRepository(session).get(conversation_id, with_messages=True)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetail.model_validate(conversation)


@router.patch("/{conversation_id}", response_model=ConversationRead)
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    session: Session = Depends(get_session),
) -> ConversationRead:
    conversation = ConversationRepository(session).get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if payload.title is not None:
        conversation.title = payload.title.strip()
    if payload.archived is not None:
        conversation.archived = payload.archived
    session.commit()
    return ConversationRead.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, session: Session = Depends(get_session)) -> Response:
    repository = ConversationRepository(session)
    conversation = repository.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    repository.delete(conversation)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED
)
def create_message(
    conversation_id: str,
    payload: MessageCreate,
    session: Session = Depends(get_session),
) -> MessageRead:
    conversations = ConversationRepository(session)
    conversation = conversations.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    attachments: list[Attachment] = []
    for attachment_id in payload.attachment_ids:
        attachment = session.get(Attachment, attachment_id)
        if attachment is None:
            raise HTTPException(status_code=404, detail=f"Attachment not found: {attachment_id}")
        if attachment.message_id is not None:
            raise HTTPException(
                status_code=409, detail="Attachment is already assigned to a message"
            )
        attachments.append(attachment)

    message = MessageRepository(session).create(
        conversation_id=conversation_id, role="user", content=payload.content.strip()
    )
    for attachment in attachments:
        attachment.message_id = message.id
    conversation.updated_at = message.created_at
    session.commit()
    saved_message = MessageRepository(session).get(message.id)
    if saved_message is None:
        raise RuntimeError("Message disappeared after commit")
    return MessageRead.model_validate(saved_message)
