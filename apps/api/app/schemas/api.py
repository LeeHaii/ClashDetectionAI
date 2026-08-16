from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=200)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = None


class AttachmentRead(ORMModel):
    id: str
    original_filename: str
    media_type: str
    size_bytes: int
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=50_000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=20)


class MessageRead(ORMModel):
    id: str
    conversation_id: str
    role: str
    content: str
    status: str
    sequence: int
    created_at: datetime
    attachments: list[AttachmentRead] = Field(default_factory=list)


class ConversationRead(ORMModel):
    id: str
    title: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = Field(default_factory=list)


class ReportCreate(BaseModel):
    upload_id: str
    title: str | None = Field(default=None, max_length=255)


class ReportRead(ORMModel):
    id: str
    source_attachment_id: str
    original_filename: str
    title: str
    parse_status: str
    parser_version: str
    errors: list[dict[str, Any]]
    clash_count: int = 0
    created_at: datetime


class ClashRead(ORMModel):
    id: str
    report_id: str
    clash_id: str
    row_index: int
    image_path: str | None
    distance_raw: str | None
    distance_m: float | None
    grid: str | None
    clash_point: str | None
    elements: list[dict[str, Any]]
    source_metadata: dict[str, Any]


class InferenceRunCreate(BaseModel):
    conversation_id: str
    user_message_id: str
    clash_item_id: str | None = None


class AnalysisResultRead(ORMModel):
    id: str
    inference_run_id: str
    normalized: dict[str, Any]
    markdown: str
    parser_version: str
    severity_rule_version: str


class InferenceRunRead(ORMModel):
    id: str
    conversation_id: str
    clash_item_id: str | None
    user_message_id: str
    assistant_message_id: str | None
    status: str
    model_name: str
    adapter_version: str
    prompt_version: str
    started_at: datetime | None
    completed_at: datetime | None
    first_token_ms: float | None
    duration_ms: float | None
    error: str | None
    cancellation_requested: bool
    result: AnalysisResultRead | None = None


class ArtifactRead(ORMModel):
    id: str
    report_id: str
    kind: str
    media_type: str
    size_bytes: int | None
    status: str
    error: str | None
    created_at: datetime


class HealthRead(BaseModel):
    status: Literal["ok", "not_ready"]
    checks: dict[str, bool] = Field(default_factory=dict)
