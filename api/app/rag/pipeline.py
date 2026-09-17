"""Grounded answer generation: rewrite → retrieve → gate → generate → validate."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.experiments import ExperimentConfig
from app.llm.base import LLMClient, Message, Timer
from app.rag.prompt import DISCLAIMER, NO_GUIDANCE, build_answer_messages
from app.rag.retriever import Retriever
from app.rag.rewrite import rewrite_query
from app.rag.types import Hit
from app.rag.validate import CORRECTIVE_NOTE, ValidationResult, validate_answer


@dataclass
class RagAnswer:
    """Everything the API returns and the research log records for a RAG turn."""

    text: str
    hits: list[Hit]
    citations: list[int]
    rewritten_query: str
    confident: bool
    top_score: float
    refused: bool
    validation_flags: list[str] = field(default_factory=list)
    attempts: int = 0
    model: str = ""
    provider: str = ""
    latency_ms: dict[str, float] = field(default_factory=dict)


def no_guidance_text() -> str:
    """The fixed low-confidence reply."""
    return f"{NO_GUIDANCE}\n\n{DISCLAIMER}"


class RagPipeline:
    """Stateless per-turn RAG orchestration over a shared retriever and LLM."""

    def __init__(self, retriever: Retriever, llm: LLMClient, cfg: ExperimentConfig) -> None:
        self.retriever = retriever
        self.llm = llm
        self.cfg = cfg

    async def answer(
        self, question: str, history: list[Message], query_override: str | None = None
    ) -> RagAnswer:
        """Answer a question from retrieved passages with enforced citations.

        `query_override` replaces the (rewritten) retrieval query, e.g. to target
        first-aid passages for a triaged dental trauma turn.
        """
        cfg = self.cfg
        latency: dict[str, float] = {}
        history = history[-cfg.max_history_turns * 2 :]

        with Timer() as t:
            if query_override:
                query = query_override
            elif cfg.rewrite_queries:
                query = await rewrite_query(self.llm, question, history, cfg.prompt_version)
            else:
                query = question
        latency["rewrite"] = t.ms

        with Timer() as t:
            retrieval = await asyncio.to_thread(self.retriever.retrieve, query, cfg.retrieval)
        latency["retrieve"] = t.ms
        latency.update({f"retrieve.{k}": v for k, v in retrieval.latency_ms.items()})

        base = RagAnswer(
            text=no_guidance_text(),
            hits=retrieval.hits,
            citations=[],
            rewritten_query=query,
            confident=retrieval.confident,
            top_score=retrieval.top_score,
            refused=True,
            model=self.llm.model,
            provider=self.llm.provider,
            latency_ms=latency,
        )
        if not retrieval.confident:
            base.validation_flags = ["low_retrieval_confidence"]
            return base

        messages = build_answer_messages(question, retrieval.hits, history, cfg.prompt_version)
        result: ValidationResult | None = None
        flags: list[str] = []
        with Timer() as t:
            for attempt in range(2):
                out = await self.llm.generate(
                    messages, temperature=cfg.llm.temperature, max_tokens=cfg.llm.max_tokens
                )
                result = validate_answer(out.text, len(retrieval.hits))
                flags.extend(f"attempt{attempt + 1}:{f}" for f in result.flags)
                base.attempts = attempt + 1
                if not result.hard_fail:
                    break
                messages = [
                    *messages,
                    {"role": "assistant", "content": out.text},
                    {
                        "role": "user",
                        "content": CORRECTIVE_NOTE.format(problems=", ".join(result.flags)),
                    },
                ]
        latency["generate"] = t.ms
        base.validation_flags = flags

        assert result is not None
        if result.hard_fail:
            base.validation_flags.append("fallback_no_guidance")
            return base
        base.text = result.text
        base.citations = result.citations
        base.refused = result.is_refusal
        return base
