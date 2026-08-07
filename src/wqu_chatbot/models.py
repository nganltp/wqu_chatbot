from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class SourceChunk(BaseModel):
    id: str
    text: str
    title: str
    url: str
    source_type: Literal["procedure", "lecture"]
    category: str | None = None
    course: str | None = None
    chapter: str | None = None


class SourceDocument(BaseModel):
    """A complete source document stored locally before chunking."""

    id: str
    content: str
    title: str
    url: str
    source_type: Literal["procedure", "lecture"] = "procedure"
    category: str | None = None
    course: str | None = None
    chapter: str | None = None
    fetched_at: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)


class SourceReference(BaseModel):
    label: str
    title: str
    course: str | None = None
    chapter: str | None = None
    url: HttpUrl


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
