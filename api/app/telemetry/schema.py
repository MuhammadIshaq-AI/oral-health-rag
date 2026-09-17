"""Research log schema: one `TurnLog` record per user turn.

Content fields (raw input, transcript, rewritten query, answer) are only stored
when the session has consented to research logging; otherwise they are nulled
and only non-identifying metrics are kept (see PRIVACY.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1

#: Fields removed when consent is false.
CONTENT_FIELDS = ("raw_input", "transcript", "rewritten_query", "answer", "triage_evidence")


class RetrievedLog(BaseModel):
    """One retrieved chunk and its scores."""

    chunk_id: str
    url: str
    dense: float | None = None
    bm25: float | None = None
    rrf: float | None = None
    rerank: float | None = None


class TurnLog(BaseModel):
    """Everything needed to analyse a turn after the fact."""

    schema_version: int = SCHEMA_VERSION
    turn_id: str
    session_id: str
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds"))
    consent: bool

    # Input
    modality: str
    raw_input: str | None = None
    transcript: str | None = None
    whisper_confidence: float | None = None
    detected_language: str | None = None
    language_probability: float | None = None
    stt_model: str | None = None
    audio_duration_s: float | None = None

    # Safety
    triage_label: str
    triage_severity: str
    triage_source: str  # rules | model | rules+model
    triage_triggers: list[str] = Field(default_factory=list)
    triage_evidence: str | None = None
    halted_by_triage: bool = False

    # Retrieval
    rewritten_query: str | None = None
    retrieval_mode: str | None = None
    retrieved: list[RetrievedLog] = Field(default_factory=list)
    top_score: float | None = None
    retrieval_confident: bool | None = None

    # Generation
    answer: str | None = None
    refused: bool = False
    citations_used: list[str] = Field(default_factory=list)
    validation_flags: list[str] = Field(default_factory=list)
    generation_attempts: int = 0

    # Versions
    provider: str
    model: str
    prompt_version: str
    corpus_version: str | None
    config_name: str
    config_hash: str
    app_version: str

    # Timing
    latency_ms: dict[str, float] = Field(default_factory=dict)

    def redacted(self) -> dict[str, Any]:
        """Dump, removing content fields if consent was not given."""
        data = self.model_dump(mode="json")
        if not self.consent:
            for key in CONTENT_FIELDS:
                data[key] = None
            data["triage_triggers"] = []
        return data
