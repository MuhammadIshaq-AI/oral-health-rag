"""Word error rate of local Whisper per voice/accent and acoustic condition."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.config import ROOT
from eval.common import mean, read_jsonl

MANIFESTS = (
    ROOT / "eval" / "audio" / "generated" / "manifest.jsonl",
    ROOT / "eval" / "audio" / "recorded" / "manifest.jsonl",  # real speech, added under ethics
)


def normalise_text(text: str) -> str:
    """Lowercase, expand a few domain abbreviations, drop punctuation, collapse spaces."""
    t = text.lower().replace("’", "'")
    t = re.sub(r"\bcdbs\b", "child dental benefits schedule", t)
    t = re.sub(r"\bnsw\b", "new south wales", t)
    t = re.sub(r"[^\w\s']", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def wer(reference: str, hypothesis: str) -> float:
    """jiwer WER on normalised text."""
    import jiwer

    return float(jiwer.wer(normalise_text(reference), normalise_text(hypothesis) or "<empty>"))


def evaluate_wer(limit: int | None = None) -> dict[str, Any]:
    """Transcribe every manifest item and aggregate WER by voice x condition."""
    import jiwer

    from app.stt.whisper import get_stt

    rows = [r for m in MANIFESTS if m.exists() for r in read_jsonl(m)]
    if not rows:
        return {"skipped": "no audio manifest; run `make audio` first"}
    rows = rows[:limit] if limit else rows
    stt = get_stt()
    groups: dict[tuple[str, str], dict[str, list[Any]]] = defaultdict(
        lambda: {"ref": [], "hyp": [], "conf": [], "latency": []}
    )
    examples = []
    for r in rows:
        result = stt.transcribe_bytes(Path(ROOT / r["path"]).read_bytes(), language="en")
        g = groups[(r["voice"], r["condition"])]
        g["ref"].append(normalise_text(r["reference"]))
        g["hyp"].append(normalise_text(result.text) or "<empty>")
        g["conf"].append(result.confidence)
        g["latency"].append(result.latency_ms)
        item_wer = wer(r["reference"], result.text)
        if item_wer > 0.2 and len(examples) < 12:
            examples.append(
                {
                    "id": r["id"],
                    "reference": r["reference"],
                    "hypothesis": result.text,
                    "wer": round(item_wer, 3),
                }
            )

    table = []
    for (voice, cond), g in sorted(groups.items()):
        table.append(
            {
                "voice": voice,
                "condition": cond,
                "n": len(g["ref"]),
                "wer": round(float(jiwer.wer(g["ref"], g["hyp"])), 4),
                "confidence_mean": round(mean(g["conf"]) or 0.0, 4),
                "latency_ms_mean": round(mean(g["latency"]) or 0.0, 1),
            }
        )
    by_condition = {}
    for cond in sorted({c for _, c in groups}):
        refs = [x for (_, c), g in groups.items() if c == cond for x in g["ref"]]
        hyps = [x for (_, c), g in groups.items() if c == cond for x in g["hyp"]]
        by_condition[cond] = round(float(jiwer.wer(refs, hyps)), 4)
    return {
        "whisper_model": stt.model_name,
        "device": getattr(stt, "device", "?"),
        "n_items": len(rows),
        "table": table,
        "by_condition": by_condition,
        "worst_examples": examples,
    }
