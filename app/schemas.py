"""Request/response models for the chat API."""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class Source(BaseModel):
    topic: str | None = None
    question: str | None = None
    answer: str | None = None
    score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    intent: str  # "rag" | "tool"
    sources: list[Source] = []
    tools_used: list[str] = []


class FeedbackRequest(BaseModel):
    conversation_id: str
    rating: int  # +1 / -1
    comment: str | None = None
