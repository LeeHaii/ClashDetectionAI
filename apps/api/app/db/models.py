from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.sequence"
    )
    runs: Mapped[list[InferenceRun]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="completed")
    sequence: Mapped[int] = mapped_column(Integer)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    attachments: Mapped[list[Attachment]] = relationship(back_populates="message")


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    report_id: Mapped[str | None] = mapped_column(
        ForeignKey("uploaded_reports.id", ondelete="CASCADE"), nullable=True, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    purpose: Mapped[str] = mapped_column(String(40), default="upload")
    storage_path: Mapped[str] = mapped_column(String(1_024), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)

    message: Mapped[Message | None] = relationship(back_populates="attachments")
    report: Mapped[UploadedReport | None] = relationship(
        back_populates="attachments", foreign_keys=[report_id]
    )


class UploadedReport(TimestampMixin, Base):
    __tablename__ = "uploaded_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    original_filename: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    parse_status: Mapped[str] = mapped_column(String(20), default="pending")
    parser_version: Mapped[str] = mapped_column(String(80))
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="report", foreign_keys=[Attachment.report_id]
    )
    clashes: Mapped[list[ClashItem]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="ClashItem.row_index"
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class ClashItem(TimestampMixin, Base):
    __tablename__ = "clash_items"
    __table_args__ = (UniqueConstraint("report_id", "clash_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("uploaded_reports.id", ondelete="CASCADE"), index=True
    )
    clash_id: Mapped[str] = mapped_column(String(255))
    row_index: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str | None] = mapped_column(String(1_024), nullable=True)
    distance_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    grid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    clash_point: Mapped[str | None] = mapped_column(String(255), nullable=True)
    elements: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    report: Mapped[UploadedReport] = relationship(back_populates="clashes")
    runs: Mapped[list[InferenceRun]] = relationship(back_populates="clash_item")


class InferenceRun(TimestampMixin, Base):
    __tablename__ = "inference_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    clash_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("clash_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="RESTRICT"))
    assistant_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    model_name: Mapped[str] = mapped_column(String(255))
    adapter_version: Mapped[str] = mapped_column(String(255))
    prompt_version: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_token_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)

    conversation: Mapped[Conversation] = relationship(back_populates="runs")
    clash_item: Mapped[ClashItem | None] = relationship(back_populates="runs")
    result: Mapped[AnalysisResult | None] = relationship(
        back_populates="run", cascade="all, delete-orphan", uselist=False
    )


class AnalysisResult(TimestampMixin, Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    inference_run_id: Mapped[str] = mapped_column(
        ForeignKey("inference_runs.id", ondelete="CASCADE"), unique=True
    )
    raw_model_output: Mapped[str] = mapped_column(Text)
    normalized: Mapped[dict[str, Any]] = mapped_column(JSON)
    markdown: Mapped[str] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(String(80))
    severity_rule_version: Mapped[str] = mapped_column(String(80))

    run: Mapped[InferenceRun] = relationship(back_populates="result")


class Artifact(TimestampMixin, Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("uploaded_reports.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), default="pdf")
    storage_path: Mapped[str | None] = mapped_column(String(1_024), nullable=True)
    media_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped[UploadedReport] = relationship(back_populates="artifacts")
