"""Per-turn orchestration shared by the HTTP API and the evaluation harness."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from app import __version__
from app.config import Settings
from app.experiments import ExperimentConfig
from app.llm.base import LLMClient, Message, Timer
from app.rag.pipeline import RagAnswer, RagPipeline
from app.rag.retriever import Retriever
from app.safety.classifier import classify_model
from app.safety.labels import HALTING
from app.safety.responses import AVULSION_FALLBACK, AVULSION_QUERY, halted_message
from app.safety.rules import classify_rules
from app.safety.triage import TriageDecision, combine
from app.schemas import ChatRequest, ChatResponse, SourceOut
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


async def _triage_and_answer(
    state: AppState, message: str, history: list[Message]
) -> tuple[TriageDecision, RagAnswer | None]:
    """Run safety triage before the dental flow, without paying for it in latency.

    Rules run first (microseconds). If they already require halting, RAG never
    starts. Otherwise the model second opinion runs *concurrently* with RAG; if the
    model escalates to a halting label, the RAG result is discarded unseen.
    """
    cfg = state.cfg
    with Timer() as t_rules:
        rules = classify_rules(message)
    use_model = cfg.triage.use_model and rules.label not in HALTING
    model_task = (
        asyncio.create_task(classify_model(state.llm, message, cfg.prompt_version))
        if use_model
        else None
    )

    rag_task: asyncio.Task[RagAnswer] | None = None
    if rules.label not in HALTING:
        if state.retriever is None:
            if model_task:
                model_task.cancel()
            raise RuntimeError("No corpus index loaded. Run `make ingest` first.")
        override = (
            f"{AVULSION_QUERY}. {message}"
            if rules.label == "dental_trauma_avulsion" and cfg.triage.corpus_first_aid
            else None
        )
        pipeline = RagPipeline(state.retriever, state.llm, cfg)
        rag_task = asyncio.create_task(pipeline.answer(message, history, query_override=override))

    with Timer() as t_model:
        model = await model_task if model_task else None
    decision = combine(rules, model, t_rules.ms + (t_model.ms if model_task else 0.0))

    if decision.halts:
        if rag_task:
            rag_task.cancel()
        return decision, None
    assert rag_task is not None
    return decision, await rag_task


async def handle_turn(state: AppState, req: ChatRequest) -> ChatResponse:
    """Run one user turn through the pipeline, log it, and build the response."""
    turn_id = uuid.uuid4().hex
    history: list[Message] = [{"role": t.role, "content": t.content} for t in req.history]
    latency: dict[str, float] = {}
    if req.stt and req.stt.latency_ms is not None:
        latency["stt"] = req.stt.latency_ms

    with Timer() as total:
        decision, rag = await _triage_and_answer(state, req.message, history)
        latency["triage"] = decision.latency_ms
        extra_flags: list[str] = []
        answer, sources, refused = halted_message(decision.label), [], False
        if rag is not None:
            latency.update(rag.latency_ms)
            answer, refused = rag.text, rag.refused
            sources = [] if rag.refused else sources_from(rag)
            if decision.label == "dental_trauma_avulsion" and rag.refused:
                answer, refused = AVULSION_FALLBACK, False
                extra_flags.append("avulsion_fallback_template")
    latency["total"] = total.ms + latency.get("stt", 0.0)

    response = ChatResponse(
        turn_id=turn_id,
        answer=answer,
        sources=sources,
        refused=refused,
        triage=decision.to_out(),
        rewritten_query=rag.rewritten_query if rag else None,
        latency_ms={k: round(v, 1) for k, v in latency.items()},
        model=state.llm.model,
        corpus_version=state.corpus_version or "",
        config_hash=state.cfg.config_hash,
    )
    record = build_turn_log(state, req, response, rag, decision)
    record.validation_flags.extend(extra_flags)
    await state.logger.log_turn(record)
    return response


def build_turn_log(
    state: AppState,
    req: ChatRequest,
    resp: ChatResponse,
    rag: RagAnswer | None,
    decision: TriageDecision,
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
        triage_source=decision.source,
        triage_triggers=decision.triggers,
        triage_evidence=decision.model_evidence,
        triage_rule_label=decision.rule_label,
        triage_model_label=decision.model_label,
        triage_model_confidence=decision.model_confidence,
        triage_model_error=decision.model_error,
        halted_by_triage=resp.triage.halted,
        rewritten_query=rag.rewritten_query if rag else None,
        retrieval_mode=state.cfg.retrieval.mode if rag else None,
        retrieved=[RetrievedLog(**h.log_record()) for h in rag.hits] if rag else [],  # type: ignore[arg-type]
        top_score=rag.top_score if rag else None,
        retrieval_confident=rag.confident if rag else None,
        answer=resp.answer,
        refused=resp.refused,
        citations_used=[s.chunk_id for s in resp.sources if s.cited],
        validation_flags=list(rag.validation_flags) if rag else [],
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
