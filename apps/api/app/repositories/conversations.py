from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Conversation, Message


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, *, archived: bool, search: str | None = None) -> list[Conversation]:
        statement: Select[tuple[Conversation]] = select(Conversation).where(
            Conversation.archived.is_(archived)
        )
        if search:
            statement = statement.where(Conversation.title.ilike(f"%{search.strip()}%"))
        statement = statement.order_by(Conversation.updated_at.desc())
        return list(self.session.scalars(statement))

    def get(self, conversation_id: str, *, with_messages: bool = False) -> Conversation | None:
        statement = select(Conversation).where(Conversation.id == conversation_id)
        if with_messages:
            statement = statement.options(
                selectinload(Conversation.messages).selectinload(Message.attachments)
            )
        return self.session.scalar(statement)

    def create(self, title: str) -> Conversation:
        conversation = Conversation(title=title.strip())
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def delete(self, conversation: Conversation) -> None:
        self.session.delete(conversation)


class MessageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, message_id: str) -> Message | None:
        return self.session.scalar(
            select(Message)
            .where(Message.id == message_id)
            .options(selectinload(Message.attachments))
        )

    def next_sequence(self, conversation_id: str) -> int:
        highest = self.session.scalar(
            select(func.max(Message.sequence)).where(Message.conversation_id == conversation_id)
        )
        return int(highest or 0) + 1

    def create(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        status: str = "completed",
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            status=status,
            sequence=self.next_sequence(conversation_id),
        )
        self.session.add(message)
        self.session.flush()
        return message
