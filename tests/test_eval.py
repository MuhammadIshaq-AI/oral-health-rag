"""Unit tests for evaluation metrics (no models, no network)."""

from __future__ import annotations

import numpy as np
import pytest

from app.llm.providers import FakeClient
from eval.common import CachedLLM, fk_grade, gold_questions, plain_text, read_jsonl, word_count
from eval.groundedness import score_judgement, summarise
from eval.retrieval import hit_at_k, ranked_urls, recall_at_k, reciprocal_rank
from eval.triage_eval import per_label_metrics
from eval.wer import normalise_text, wer


def test_retrieval_metrics() -> None:
    ranked = ranked_urls(["a", "a", "b", "c", "b", "d"])
    assert ranked == ["a", "b", "c", "d"]
    rel = {"b", "d"}
    assert recall_at_k(ranked, rel, 1) == 0.0
    assert recall_at_k(ranked, rel, 2) == 0.5
    assert recall_at_k(ranked, rel, 4) == 1.0
    assert hit_at_k(ranked, rel, 2) == 1.0
    assert reciprocal_rank(ranked, rel) == 0.5
    assert reciprocal_rank(ranked, {"z"}) == 0.0


def test_gold_file_shape() -> None:
    labelled = gold_questions()
    everything = gold_questions(include_todo=True)
    assert len(labelled) >= 20 and len(everything) >= 100
    assert all(g["relevant_urls"] for g in labelled)
    assert len({g["id"] for g in everything}) == len(everything)


def test_extra_questions_categories() -> None:
    from eval.common import EVAL_DIR

    cats = {x["category"] for x in read_jsonl(EVAL_DIR / "questions_extra.jsonl")}
    assert cats <= {"unanswerable", "unsafe", "out_of_scope"}


def test_score_and_summarise_judgements() -> None:
    j = {
        "sentences": [
            {"i": 1, "needs_support": True, "verdict": "supported", "citations": {"1": True}},
            {
                "i": 2,
                "needs_support": True,
                "verdict": "partial",
                "citations": {"1": False, "2": True},
            },
            {"i": 3, "needs_support": True, "verdict": "unsupported", "citations": {}},
            {"i": 4, "needs_support": False},
        ],
        "declined": False,
        "diagnoses": False,
    }
    s = score_judgement(j, with_citations=True)
    assert (s["needs_support"], s["supported"], s["partial"]) == (3, 1, 1)
    assert (s["citation_pairs"], s["citation_pairs_supported"]) == (3, 2)
    assert s["sentences_with_supporting_citation"] == 2

    row = {
        "category": "in_scope",
        "declined": False,
        "scores": s,
        "fk_grade": 7.0,
        "words": 50,
        "latency_ms": 10.0,
    }
    probe = {**row, "category": "unsafe", "declined": True, "scores": {**s, "diagnoses": False}}
    summary = summarise([row, probe], with_citations=True)
    assert summary["faithfulness_strict"] == pytest.approx(1 / 3, abs=1e-4)
    assert summary["faithfulness_lenient"] == pytest.approx(0.5, abs=1e-4)
    assert summary["citation_precision"] == pytest.approx(2 / 3, abs=1e-4)
    assert summary["citation_recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert summary["unsafe_probe_decline_rate"] == 1.0 and summary["over_refusal_rate"] == 0.0


def test_plain_text_and_readability() -> None:
    answer = "**Brush** twice a day [1].\n- Floss daily [2]\n\nThis is general information, not dental advice."
    assert plain_text(answer) == "Brush twice a day. Floss daily."
    assert word_count(answer) == 6
    assert fk_grade("The cat sat on the mat.") < 3


def test_wer_normalisation() -> None:
    assert (
        normalise_text("Is my child eligible for the CDBS?")
        == "is my child eligible for the child dental benefits schedule"
    )
    assert wer("How do I clean my dentures?", "how do i clean my dentures") == 0.0
    assert wer("How do I clean my dentures?", "how do i clean my dent yours") == pytest.approx(
        2 / 6
    )


def test_triage_metrics() -> None:
    m = per_label_metrics(["none", "urgent_swelling", "none"], ["none", "none", "urgent_swelling"])
    assert m["none"]["recall"] == 0.5 and m["urgent_swelling"]["precision"] == 0.0


def test_audio_transforms() -> None:
    from eval.audio.synth import add_noise, resample, telephone

    sr = 16_000
    t = np.arange(sr) / sr
    tone = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    low = (0.5 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)
    assert len(resample(tone, sr, 8000)) == 8000
    noisy = add_noise(tone, 10.0, seed=1)
    snr = 10 * np.log10(np.mean(tone**2) / np.mean((noisy - tone) ** 2))
    assert 9.0 < snr < 11.0
    assert np.sqrt(np.mean(telephone(low, sr) ** 2)) < 0.05  # 100 Hz is outside the phone band
    assert np.sqrt(np.mean(telephone(tone, sr) ** 2)) > 0.25  # 1 kHz passes


async def test_cached_llm(tmp_path, monkeypatch) -> None:
    import eval.common as common

    monkeypatch.setattr(common, "CACHE_DIR", tmp_path)
    inner = FakeClient(responses=["first", "second"])
    cached = CachedLLM(inner, "t")
    msgs = [{"role": "user", "content": "hi"}]
    assert (await cached.generate(msgs)).text == "first"
    assert (await cached.generate(msgs)).text == "first"  # served from disk
    assert cached.hits == 1 and cached.misses == 1 and len(inner.calls) == 1
