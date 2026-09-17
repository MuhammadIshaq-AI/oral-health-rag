"""Public API request/response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Modality = Literal["text", "voice", "voice_upload"]


class HistoryTurn(BaseModel):
    """A previous chat turn sent by the client."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=6000)


class STTMeta(BaseModel):
    """Speech-to-text metadata attached to voice turns."""

    transcript: str
    language: str | None = None
    language_probability: float | None = None
    confidence: float | None = None
    duration_s: float | None = None
    latency_ms: float | None = None
    model: str | None = None


class ChatRequest(BaseModel):
    """One user turn."""

    session_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=24)
    modality: Modality = "text"
    stt: STTMeta | None = None


class SourceOut(BaseModel):
    """A retrieved passage shown as a citation chip."""

    n: int
    chunk_id: str
    source_org: str
    page_title: str
    section: str
    url: str
    text: str
    retrieved_at: str
    jurisdiction: str
    secondary: bool
    cited: bool
    score: float


class TriageOut(BaseModel):
    """Safety classification returned to the UI."""

    label: str
    severity: Literal["none", "info", "urgent", "emergency", "crisis"]
    title: str | None = None
    actions: list[dict[str, str]] = Field(default_factory=list)
    halted: bool = False


class ChatResponse(BaseModel):
    """Assistant reply."""

    turn_id: str
    answer: str
    sources: list[SourceOut]
    refused: bool
    triage: TriageOut
    rewritten_query: str | None = None
    latency_ms: dict[str, float]
    model: str
    corpus_version: str
    config_hash: str


class SessionOut(BaseModel):
    """New anonymous session."""

    session_id: str


class ConsentIn(BaseModel):
    """Consent decision for research logging."""

    session_id: str = Field(min_length=8, max_length=64)
    consent: bool


class HealthOut(BaseModel):
    """Service status."""

    status: str
    model: str
    provider: str
    local_only: bool
    corpus_version: str | None
    n_chunks: int
    vector_store: str | None
    retrieval_mode: str
    config_name: str
    config_hash: str
    prompt_version: str
    tts_enabled: bool
    whisper_model: str
