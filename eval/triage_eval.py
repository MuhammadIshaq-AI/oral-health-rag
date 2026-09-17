"""Triage evaluation on the labelled synthetic utterances (rules, and optionally rules + model)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.experiments import TriageConfig
from app.llm.base import LLMClient
from app.safety.labels import HALTING, PRECEDENCE
from app.safety.triage import triage
from eval.common import ROOT, read_jsonl


def per_label_metrics(gold: list[str], pred: list[str]) -> dict[str, dict[str, float | int]]:
    """Precision / recall / F1 / support per label."""
    out: dict[str, dict[str, float | int]] = {}
    for label in PRECEDENCE:
        tp = sum(g == p == label for g, p in zip(gold, pred, strict=True))
        fp = sum(p == label and g != label for g, p in zip(gold, pred, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, pred, strict=True))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[label] = {
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1": round(f1, 3),
            "support": tp + fn,
        }
    return out


async def evaluate_triage(llm: LLMClient | None, use_model: bool) -> dict[str, Any]:
    """Accuracy, per-label metrics, halting-label recall and under-triage count."""
    cases = read_jsonl(ROOT / "tests" / "triage_cases.jsonl")
    cfg = TriageConfig(use_model=use_model)
    preds = []
    for c in cases:
        d = await triage(c["text"], cfg, llm)
        preds.append(d.label)
    gold = [c["label"] for c in cases]
    rank = {label: i for i, label in enumerate(PRECEDENCE)}
    under = [
        {"id": c["id"], "text": c["text"], "gold": g, "pred": p}
        for c, g, p in zip(cases, gold, preds, strict=True)
        if rank[p] > rank[g]
    ]
    halting_gold = [p for g, p in zip(gold, preds, strict=True) if g in HALTING]
    return {
        "mode": "rules+model" if use_model else "rules",
        "n": len(cases),
        "accuracy": round(sum(g == p for g, p in zip(gold, preds, strict=True)) / len(cases), 4),
        "halting_recall": round(sum(p in HALTING for p in halting_gold) / len(halting_gold), 4),
        "under_triage": under,
        "confusion": dict(Counter(f"{g}->{p}" for g, p in zip(gold, preds, strict=True) if g != p)),
        "per_label": per_label_metrics(gold, preds),
    }
