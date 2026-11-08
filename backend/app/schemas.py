"""Esquemas de entrada y salida de la API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SourceType = Literal["pdf", "docx", "pptx", "web", "youtube", "image", "text"]


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El nombre no puede estar vacio")
        return value


class SubjectOut(BaseModel):
    id: str
    name: str
    color: str
    created_at: str
    document_count: int = 0


class DocumentOut(BaseModel):
    id: str
    subject_id: str
    title: str
    original_name: str | None
    source_type: SourceType
    source_uri: str | None
    size_bytes: int
    page_count: int | None
    status: str
    progress: float
    error: str | None
    chunk_count: int
    created_at: str
    indexed_at: str | None


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subject_id: str | None = None


class UrlIngest(BaseModel):
    subject_id: str
    url: str = Field(min_length=8, max_length=2048)
    kind: Literal["web", "youtube"] = "web"


class TextIngest(BaseModel):
    subject_id: str
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=20, max_length=2_000_000)


class CitationOut(BaseModel):
    index: int
    document_id: str
    document_title: str
    source_type: SourceType
    page_from: int | None
    page_to: int | None
    heading: str | None
    snippet: str
    score: float
    locator: str | None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    subject_id: str | None = None
    document_ids: list[str] | None = None
    conversation_id: str | None = None

    @field_validator("question")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("La pregunta no puede estar vacia")
        return value


class ProviderConfig(BaseModel):
    provider: str = "gemini"
    model: str = ""
    api_key: str | None = None
    base_url: str | None = None


class ProviderOut(BaseModel):
    provider: str
    model: str
    base_url: str | None
    has_key: bool
    key_hint: str | None


class ProviderPreset(BaseModel):
    id: str
    label: str
    kind: str
    base_url: str | None
    default_model: str
    requires_key: bool
    help_url: str | None = None


class ProviderTest(BaseModel):
    ok: bool
    message: str
    models: list[str] = []


StudyKind = Literal["summary", "outline", "deck", "quiz"]


class StudyCreate(BaseModel):
    subject_id: str
    kind: StudyKind
    topic: str | None = Field(default=None, max_length=300)
    document_ids: list[str] | None = None


class CardReview(BaseModel):
    rating: int = Field(ge=1, le=4)


class QuizAnswer(BaseModel):
    chosen_index: int = Field(ge=0, le=3)
