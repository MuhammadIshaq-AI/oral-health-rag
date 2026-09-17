"""Render evaluation results as a timestamped markdown report (plus raw JSON)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import ROOT

REPORTS = ROOT / "reports"


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f}%"


def _num(x: float | None, nd: int = 3) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def render(results: dict[str, Any]) -> str:
    """Markdown report."""
    meta = results["meta"]
    lines = [
        f"# DentalCare AU evaluation report — {meta['timestamp']}",
        "",
        "## Reproducibility",
        "",
        "| Item | Value |",
        "|---|---|",
    ]
    for key in (
        "config_name",
        "config_hash",
        "provider",
        "model",
        "judge_model",
        "prompt_version",
        "corpus_version",
        "n_chunks",
        "embedding_model",
        "reranker_model",
        "git_commit",
        "command",
    ):
        lines.append(f"| {key} | `{meta.get(key, '')}` |")

    if r := results.get("retrieval"):
        lines += [
            "",
            f"## Retrieval (n = {r['n_questions']} labelled questions, page-level relevance)",
            "",
            "| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Hit@3 | MRR | Mean latency (ms) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for mode, m in r["modes"].items():
            lines.append(
                f"| {mode} | {_num(m['recall@1'])} | {_num(m['recall@3'])} | {_num(m['recall@5'])} | "
                f"{_num(m['recall@10'])} | {_num(m['hit@3'])} | {_num(m['mrr'])} | {m['latency_ms_mean']} |"
            )

    if g := results.get("groundedness"):
        rag, base = g["rag"]["summary"], g["baseline"]["summary"]
        lines += [
            "",
            "## Groundedness: RAG vs ungrounded baseline",
            "",
            f"In-scope questions: {rag['n_in_scope']}. Claims are judged sentence-by-sentence against the "
            "passages retrieved for the question (fixed rubric, `prompts/judge_v1.md`).",
            "",
            "| Metric | RAG (grounded) | Baseline (same LLM, no retrieval) |",
            "|---|---:|---:|",
        ]
        rows = [
            (
                "Faithfulness, strict (supported claims)",
                _pct(rag["faithfulness_strict"]),
                _pct(base["faithfulness_strict"]),
            ),
            (
                "Faithfulness, lenient (partial = 0.5)",
                _pct(rag["faithfulness_lenient"]),
                _pct(base["faithfulness_lenient"]),
            ),
            ("Citation precision", _pct(rag.get("citation_precision")), "n/a"),
            ("Citation recall", _pct(rag.get("citation_recall")), "n/a"),
            ("Claims judged", str(rag["claims"]), str(base["claims"])),
            (
                "Over-refusal on answerable questions",
                _pct(rag["over_refusal_rate"]),
                _pct(base["over_refusal_rate"]),
            ),
            (
                "Declines on unanswerable/unsafe/out-of-scope probes",
                _pct(rag["probe_decline_rate"]),
                _pct(base["probe_decline_rate"]),
            ),
            (
                "Declines on unsafe probes",
                _pct(rag["unsafe_probe_decline_rate"]),
                _pct(base["unsafe_probe_decline_rate"]),
            ),
            (
                "Diagnosis / prescription language (judge)",
                _pct(rag["diagnosis_or_prescription_rate"]),
                _pct(base["diagnosis_or_prescription_rate"]),
            ),
            (
                "Flesch-Kincaid grade (mean)",
                _num(rag["fk_grade_mean"], 1),
                _num(base["fk_grade_mean"], 1),
            ),
            (
                "Answer length, words (mean)",
                _num(rag["words_mean"], 0),
                _num(base["words_mean"], 0),
            ),
            (
                "Latency, ms (mean)",
                _num(rag["latency_ms_mean"], 0),
                _num(base["latency_ms_mean"], 0),
            ),
        ]
        lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
        lines += [
            "",
            "### Per-question (RAG)",
            "",
            "| ID | Category | Declined | Supported / claims | Flags |",
            "|---|---|---|---|---|",
        ]
        for row in g["rag"]["rows"]:
            s = row["scores"]
            flags = ", ".join(f for f in row["validation_flags"] if "some_uncited" not in f) or ""
            lines.append(
                f"| {row['id']} | {row['category']} | {row['declined']} | {s['supported']} / {s['needs_support']} | {flags} |"
            )

    if t := results.get("triage"):
        lines += [
            "",
            f"## Safety triage ({t['mode']}, n = {t['n']} synthetic utterances)",
            "",
            f"Accuracy **{_pct(t['accuracy'])}**, recall on halting labels (crisis/emergency) **{_pct(t['halting_recall'])}**, "
            f"under-triaged cases: **{len(t['under_triage'])}**.",
            "",
            "| Label | Precision | Recall | F1 | Support |",
            "|---|---:|---:|---:|---:|",
        ]
        for label, m in t["per_label"].items():
            lines.append(
                f"| {label} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['support']} |"
            )
        lines += [
            "",
            "> The triage rules were developed against this same synthetic set, so these figures measure "
            "regression, not generalisation. A held-out, clinician-labelled set is required for validity.",
        ]

    if w := results.get("wer"):
        if "skipped" in w:
            lines += ["", "## Speech recognition", "", f"Skipped: {w['skipped']}"]
        else:
            lines += [
                "",
                f"## Speech recognition (faster-whisper `{w['whisper_model']}` on {w['device']}, n = {w['n_items']})",
                "",
                "Synthetic Piper voices are a proxy for accents; see limitations.",
                "",
                "| Voice | Condition | N | WER | Mean confidence | Mean latency (ms) |",
                "|---|---|---:|---:|---:|---:|",
            ]
            for row in w["table"]:
                lines.append(
                    f"| {row['voice']} | {row['condition']} | {row['n']} | {_pct(row['wer'])} | {row['confidence_mean']:.3f} | {row['latency_ms_mean']} |"
                )
            lines += ["", "| Condition | WER (all voices) |", "|---|---:|"]
            lines += [f"| {c} | {_pct(v)} |" for c, v in w["by_condition"].items()]

    lines += [
        "",
        "---",
        "Generated by `make eval` (`python -m eval.run`). Raw results: the `.json` file next to this report.",
    ]
    return "\n".join(lines) + "\n"


def write_report(results: dict[str, Any]) -> tuple[Path, Path]:
    """Write reports/eval-<timestamp>.{md,json}."""
    REPORTS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    md, js = REPORTS / f"eval-{stamp}.md", REPORTS / f"eval-{stamp}.json"
    md.write_text(render(results), encoding="utf-8")
    js.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return md, js
