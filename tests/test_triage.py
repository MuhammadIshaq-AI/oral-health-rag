"""Deterministic triage rules against the labelled synthetic test set."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from app.experiments import TriageConfig
from app.llm.providers import FakeClient
from app.safety.labels import HALTING, PRECEDENCE, most_urgent
from app.safety.rules import classify_rules, normalise
from app.safety.triage import triage

CASES_PATH = Path(__file__).with_name("triage_cases.jsonl")
CASES = [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line]
CRITICAL = {"crisis_self_harm", "emergency_airway", "medical_emergency_other"}


def test_case_file_is_large_and_covers_all_labels() -> None:
    assert len(CASES) >= 100
    assert len({c["id"] for c in CASES}) == len(CASES)
    assert set(Counter(c["label"] for c in CASES)) == set(PRECEDENCE)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_rules_label(case: dict[str, str]) -> None:
    decision = classify_rules(case["text"])
    assert decision.label == case["label"], (case["text"], decision.candidates)
    if decision.label != "none":
        assert decision.triggers, "non-none decisions must carry trigger phrases"


def test_critical_recall_is_perfect() -> None:
    critical = [c for c in CASES if c["label"] in CRITICAL]
    missed = [c["id"] for c in critical if classify_rules(c["text"]).label not in CRITICAL]
    assert not missed


def test_normalise_fixes_stt_artifacts() -> None:
    assert normalise("Face SWOLEN cant breath") == "face swollen can't breathe"
    assert normalise("bad breath smells") == "bad breath smells"


def test_precedence() -> None:
    assert most_urgent("urgent_swelling", "emergency_airway") == "emergency_airway"
    assert most_urgent("none", "out_of_scope") == "out_of_scope"
    assert HALTING == CRITICAL


async def test_model_can_escalate_but_not_downgrade() -> None:
    cfg = TriageConfig(use_model=True)
    up = await triage(
        "my tooth hurts a lot",
        cfg,
        FakeClient(responses=['{"label": "urgent_swelling", "confidence": 0.7, "evidence": "x"}']),
    )
    assert up.label == "urgent_swelling" and up.source == "model"

    down = await triage(
        "I want to kill myself",
        cfg,
        FakeClient(responses=['{"label": "none", "confidence": 0.9, "evidence": ""}']),
    )
    assert down.label == "crisis_self_harm" and down.source == "rules" and down.halts


async def test_model_failure_falls_back_to_rules() -> None:
    d = await triage(
        "face swollen, can't swallow", TriageConfig(), FakeClient(responses=["not json"])
    )
    assert d.label == "emergency_airway" and d.model_error


async def test_rules_only_mode() -> None:
    llm = FakeClient()
    d = await triage("bleeding gums", TriageConfig(use_model=False), llm)
    assert d.label == "none" and llm.calls == [] and d.model_label is None
