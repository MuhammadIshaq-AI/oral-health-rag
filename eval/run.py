"""`make eval`: run retrieval, groundedness/baseline, triage and WER evaluations and write a report.

Examples
--------
    python -m eval.run                                   # config from EXPERIMENT_CONFIG
    python -m eval.run --config configs/local-qwen.yaml  # fully local, reproducible
    python -m eval.run --only retrieval,triage           # no LLM calls
    python -m eval.run --limit 5                         # smoke test
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import enable_system_tls, get_settings
from app.experiments import load_experiment
from app.llm.factory import make_llm
from app.rag.retriever import Retriever
from eval.common import CachedLLM, git_commit
from eval.report import write_report

SECTIONS = ("retrieval", "groundedness", "triage", "wer")
log = logging.getLogger("eval")


async def run(
    config: Path, only: tuple[str, ...], limit: int | None, triage_model: bool
) -> dict[str, Any]:
    """Execute the requested evaluation sections."""
    enable_system_tls()
    settings = get_settings()
    cfg = load_experiment(config)
    retriever = Retriever.from_settings(settings)
    llm = CachedLLM(make_llm(cfg.llm, settings), f"{cfg.llm.provider}-{cfg.llm.model}")
    judge_cfg = cfg.judge_llm or cfg.llm
    judge = CachedLLM(
        make_llm(judge_cfg, settings), f"judge-{judge_cfg.provider}-{judge_cfg.model}"
    )

    results: dict[str, Any] = {
        "meta": {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "config_name": cfg.name,
            "config_hash": cfg.config_hash,
            "config": cfg.model_dump(mode="json"),
            "provider": cfg.llm.provider,
            "model": cfg.llm.model,
            "judge_model": f"{judge_cfg.provider}/{judge_cfg.model}",
            "prompt_version": cfg.prompt_version,
            "corpus_version": retriever.corpus_version[:12],
            "n_chunks": len(retriever.chunks),
            "embedding_model": settings.embedding_model,
            "reranker_model": settings.reranker_model,
            "vector_store": retriever.store_name,
            "git_commit": git_commit(),
            "command": " ".join(["python -m eval.run", *sys.argv[1:]]),
            "limit": limit,
        }
    }
    if "retrieval" in only:
        log.info("== retrieval")
        from eval.retrieval import evaluate_retrieval

        results["retrieval"] = evaluate_retrieval(retriever, cfg, limit)
    if "triage" in only:
        log.info("== triage (%s)", "rules+model" if triage_model else "rules")
        from eval.triage_eval import evaluate_triage

        results["triage"] = await evaluate_triage(llm, use_model=triage_model)
    if "groundedness" in only:
        log.info("== groundedness + baseline")
        from eval.groundedness import evaluate_groundedness

        results["groundedness"] = await evaluate_groundedness(retriever, cfg, llm, judge, limit)
    if "wer" in only:
        log.info("== speech recognition")
        from eval.wer import evaluate_wer

        results["wer"] = await asyncio.to_thread(evaluate_wer, None)
    results["meta"]["llm_cache"] = {
        "hits": llm.hits + judge.hits,
        "misses": llm.misses + judge.misses,
    }
    return results


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for noisy in ("httpx", "sentence_transformers", "faiss", "faster_whisper"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    settings = get_settings()
    ap = argparse.ArgumentParser(description="DentalCare AU evaluation harness")
    ap.add_argument("--config", type=Path, default=settings.experiment_config)
    ap.add_argument("--only", default=",".join(SECTIONS), help=f"comma list of {SECTIONS}")
    ap.add_argument(
        "--limit", type=int, default=None, help="max questions per section (smoke test)"
    )
    ap.add_argument(
        "--triage-model", action="store_true", help="also query the LLM for each triage case"
    )
    args = ap.parse_args()
    only = tuple(s.strip() for s in args.only.split(",") if s.strip())
    unknown = set(only) - set(SECTIONS)
    if unknown:
        ap.error(f"unknown sections: {unknown}")
    results = asyncio.run(run(settings.resolve(args.config), only, args.limit, args.triage_model))
    md, js = write_report(results)
    print(f"Report: {md}\nRaw:    {js}")


if __name__ == "__main__":
    main()
