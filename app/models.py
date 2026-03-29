from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceSnippet(BaseModel):
    chunk_id: str
    source_label: str
    score: float
    text: str


class ChatDebugInfo(BaseModel):
    used_fallback: bool
    score_threshold: float
    top_score: float | None = None
    matches: list[SourceSnippet] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    title: str | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    document_name: str | None = None
    document_type: str | None = None
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    sources: list[SourceSnippet] = Field(default_factory=list)


class ConversationDetail(BaseModel):
    conversation: ConversationSummary
    messages: list[MessageResponse]


class UploadResponse(BaseModel):
    conversation_id: str
    filename: str
    chunk_count: int


class ChatRequest(BaseModel):
    conversation_id: str
    message: str = Field(min_length=1)
    debug: bool = False


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceSnippet] = Field(default_factory=list)
    debug: ChatDebugInfo | None = None


class FrontendConfigResponse(BaseModel):
    firebase_enabled: bool
    firebase: dict[str, str]
