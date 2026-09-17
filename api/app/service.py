"""Per-turn orchestration shared by the HTTP API and the evaluation harness."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app import __version__
from app.config import Settings
from app.experiments import ExperimentConfig
from app.llm.base import LLMClient, Message, Timer
from app.rag.pipeline import RagAnswer, RagPipeline
from app.rag.retriever import Retriever
from app.schemas import ChatRequest, ChatResponse, SourceOut, TriageOut
from app.telemetry.logger import ResearchLogger
from app.telemetry.schema import RetrievedLog, TurnLog


@dataclass
class AppState:
    """Long-lived objects created at startup."""

    settings: Settings
    cfg: ExperimentConfig
    llm: LLMClient
    retriever: Retriever | None
    logger: ResearchLogger

    @property
    def corpus_version(self) -> str | None:
        """Active corpus version, if an index is loaded."""
        return self.retriever.corpus_version if self.retriever else None


def sources_from(answer: RagAnswer) -> list[SourceOut]:
    """Convert hits to numbered citation sources."""
    return [
        SourceOut(
            n=i,
            chunk_id=h.chunk.chunk_id,
            source_org=h.chunk.source_org,
            page_title=h.chunk.page_title,
            section=h.chunk.section,
            url=h.chunk.url,
            text=h.chunk.text,
            retrieved_at=h.chunk.retrieved_at,
            jurisdiction=h.chunk.jurisdiction,
            secondary=h.chunk.secondary,
            cited=i in answer.citations,
            score=round(h.score, 4),
        )
        for i, h in enumerate(answer.hits, start=1)
    ]


async def handle_turn(state: AppState, req: ChatRequest) -> ChatResponse:
    """Run one user turn through the pipeline, log it, and build the response."""
    turn_id = uuid.uuid4().hex
    history: list[Message] = [{"role": t.role, "content": t.content} for t in req.history]
    latency: dict[str, float] = {}
    if req.stt and req.stt.latency_ms is not None:
        latency["stt"] = req.stt.latency_ms

    with Timer() as total:
        if state.retriever is None:
            raise RuntimeError("No corpus index loaded. Run `make ingest` first.")
        rag = await RagPipeline(state.retriever, state.llm, state.cfg).answer(req.message, history)
        latency.update(rag.latency_ms)
        triage = TriageOut(label="none", severity="none")
        sources = sources_from(rag)
    latency["total"] = total.ms + latency.get("stt", 0.0)

    response = ChatResponse(
        turn_id=turn_id,
        answer=rag.text,
        sources=sources if not rag.refused else [],
        refused=rag.refused,
        triage=triage,
        rewritten_query=rag.rewritten_query,
        latency_ms={k: round(v, 1) for k, v in latency.items()},
        model=rag.model,
        corpus_version=state.corpus_version or "",
        config_hash=state.cfg.config_hash,
    )
    await state.logger.log_turn(build_turn_log(state, req, response, rag, triage_source="none"))
    return response


def build_turn_log(
    state: AppState,
    req: ChatRequest,
    resp: ChatResponse,
    rag: RagAnswer | None,
    triage_source: str,
    triage_triggers: list[str] | None = None,
    triage_evidence: str | None = None,
) -> TurnLog:
    """Assemble the research record for a turn."""
    stt = req.stt
    return TurnLog(
        turn_id=resp.turn_id,
        session_id=req.session_id,
        consent=state.logger.consent_for(req.session_id),
        modality=req.modality,
        raw_input=req.message,
        transcript=stt.transcript if stt else None,
        whisper_confidence=stt.confidence if stt else None,
        detected_language=stt.language if stt else None,
        language_probability=stt.language_probability if stt else None,
        stt_model=stt.model if stt else None,
        audio_duration_s=stt.duration_s if stt else None,
        triage_label=resp.triage.label,
        triage_severity=resp.triage.severity,
        triage_source=triage_source,
        triage_triggers=triage_triggers or [],
        triage_evidence=triage_evidence,
        halted_by_triage=resp.triage.halted,
        rewritten_query=rag.rewritten_query if rag else None,
        retrieval_mode=state.cfg.retrieval.mode if rag else None,
        retrieved=[RetrievedLog(**h.log_record()) for h in rag.hits] if rag else [],  # type: ignore[arg-type]
        top_score=rag.top_score if rag else None,
        retrieval_confident=rag.confident if rag else None,
        answer=resp.answer,
        refused=resp.refused,
        citations_used=[s.chunk_id for s in resp.sources if s.cited],
        validation_flags=rag.validation_flags if rag else [],
        generation_attempts=rag.attempts if rag else 0,
        provider=state.llm.provider,
        model=state.llm.model,
        prompt_version=state.cfg.prompt_version,
        corpus_version=state.corpus_version,
        config_name=state.cfg.name,
        config_hash=state.cfg.config_hash,
        app_version=__version__,
        latency_ms=resp.latency_ms,
    )
