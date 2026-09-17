"""Retrieval evaluation: recall@k and MRR against URL-level relevance labels."""

from __future__ import annotations

import time
from typing import Any

from app.experiments import ExperimentConfig
from app.rag.retriever import Retriever
from eval.common import gold_questions, mean

KS = (1, 3, 5, 10)
MODES = ("dense", "hybrid", "rerank")


def ranked_urls(urls: list[str]) -> list[str]:
    """De-duplicate chunk URLs, keeping first (best) rank per page."""
    return list(dict.fromkeys(urls))


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """|relevant ∩ top-k pages| / |relevant|."""
    return len(set(ranked[:k]) & relevant) / len(relevant) if relevant else 0.0


def hit_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """1 if any relevant page is in the top-k."""
    return float(bool(set(ranked[:k]) & relevant))


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    """1 / rank of the first relevant page (0 if none retrieved)."""
    for i, url in enumerate(ranked, start=1):
        if url in relevant:
            return 1.0 / i
    return 0.0


def evaluate_retrieval(
    retriever: Retriever, cfg: ExperimentConfig, limit: int | None = None
) -> dict[str, Any]:
    """Run every retrieval mode over the labelled gold questions."""
    gold = gold_questions()[:limit]
    results: dict[str, Any] = {"n_questions": len(gold), "modes": {}, "per_question": []}
    per_q: dict[str, dict[str, Any]] = {
        g["id"]: {"id": g["id"], "question": g["question"]} for g in gold
    }

    for mode in MODES:
        rcfg = cfg.retrieval.model_copy(
            update={"mode": mode, "final_k": 30, "rerank_candidates": 30}
        )
        rows: dict[str, list[float]] = {f"recall@{k}": [] for k in KS}
        rows.update({f"hit@{k}": [] for k in KS})
        rows["mrr"] = []
        latencies: list[float] = []
        for g in gold:
            relevant = set(g["relevant_urls"])
            t0 = time.perf_counter()
            res = retriever.retrieve(g["question"], rcfg)
            latencies.append((time.perf_counter() - t0) * 1000)
            ranked = ranked_urls([h.chunk.url for h in res.hits])
            for k in KS:
                rows[f"recall@{k}"].append(recall_at_k(ranked, relevant, k))
                rows[f"hit@{k}"].append(hit_at_k(ranked, relevant, k))
            rr = reciprocal_rank(ranked, relevant)
            rows["mrr"].append(rr)
            per_q[g["id"]][f"{mode}_rr"] = round(rr, 3)
            per_q[g["id"]][f"{mode}_top3"] = ranked[:3]
        summary = {name: round(mean(vals) or 0.0, 4) for name, vals in rows.items()}
        summary["latency_ms_mean"] = round(mean(latencies[1:] or latencies) or 0.0, 1)
        results["modes"][mode] = summary
    results["per_question"] = list(per_q.values())
    return results
