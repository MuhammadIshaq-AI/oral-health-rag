"""HTTP API tests with an injected fake state (no models, no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.experiments import ExperimentConfig, RetrievalConfig, TriageConfig
from app.llm.providers import FakeClient
from app.main import app
from app.service import AppState
from app.telemetry.logger import ResearchLogger


@pytest.fixture
def client(retriever, tmp_path: Path):
    import asyncio

    logger = ResearchLogger(tmp_path / "logs")
    asyncio.run(logger.init())
    cfg = ExperimentConfig(
        name="test",
        retrieval=RetrievalConfig(mode="hybrid", min_dense_score=0.0, final_k=3),
        triage=TriageConfig(use_model=False),
    )
    app.state.svc = AppState(
        settings=Settings(data_dir=tmp_path, log_dir=tmp_path / "logs"),
        cfg=cfg,
        llm=FakeClient(),
        retriever=retriever,
        logger=logger,
    )
    with TestClient(app) as c:
        yield c
    del app.state.svc


def _session(client: TestClient, consent: bool = True) -> str:
    sid = client.post("/api/session").json()["session_id"]
    assert client.post("/api/consent", json={"session_id": sid, "consent": consent}).json()["ok"]
    return sid


def _records(tmp_path: Path) -> list[dict]:
    files = list((tmp_path / "logs").glob("turns-*.jsonl"))
    return [json.loads(line) for f in files for line in f.read_text(encoding="utf-8").splitlines()]


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["n_chunks"] == 5 and body["config_name"] == "test"


def test_chat_cited_and_logged(client: TestClient, tmp_path: Path) -> None:
    sid = _session(client)
    r = client.post("/api/chat", json={"session_id": sid, "message": "why do my gums bleed?"})
    assert r.status_code == 200
    body = r.json()
    assert body["sources"] and any(s["cited"] for s in body["sources"])
    assert body["triage"]["label"] == "none"
    rec = _records(tmp_path)[-1]
    assert rec["consent"] is True and rec["raw_input"] == "why do my gums bleed?"
    assert rec["retrieved"] and rec["config_hash"] and rec["latency_ms"]["total"] > 0


def test_no_consent_redacts_content(client: TestClient, tmp_path: Path) -> None:
    sid = _session(client, consent=False)
    client.post("/api/chat", json={"session_id": sid, "message": "dry mouth at night"})
    rec = _records(tmp_path)[-1]
    assert rec["consent"] is False
    assert rec["raw_input"] is None and rec["answer"] is None and rec["rewritten_query"] is None
    assert rec["retrieved"]  # non-content metrics are still kept


def test_emergency_halts_before_rag(client: TestClient, tmp_path: Path) -> None:
    sid = _session(client)
    body = client.post(
        "/api/chat", json={"session_id": sid, "message": "my face is swollen and I can't breathe"}
    ).json()
    assert body["triage"]["label"] == "emergency_airway" and body["triage"]["halted"]
    assert "000" in body["answer"] and body["sources"] == []
    assert any(a["href"] == "tel:000" for a in body["triage"]["actions"])
    rec = _records(tmp_path)[-1]
    assert rec["halted_by_triage"] and rec["retrieved"] == [] and rec["triage_triggers"]


def test_crisis_redirects(client: TestClient) -> None:
    sid = _session(client)
    body = client.post("/api/chat", json={"session_id": sid, "message": "I want to die"}).json()
    assert body["triage"]["severity"] == "crisis" and "13 11 14" in body["answer"]


def test_avulsion_answers_from_corpus_with_banner(client: TestClient) -> None:
    sid = _session(client)
    body = client.post(
        "/api/chat", json={"session_id": sid, "message": "my son's adult tooth got knocked out"}
    ).json()
    assert body["triage"]["label"] == "dental_trauma_avulsion" and not body["triage"]["halted"]
    assert body["triage"]["message"] and body["sources"]
    assert body["sources"][0]["chunk_id"] == "healthdirect-knocked-out-tooth#00"


def test_validation_error(client: TestClient) -> None:
    assert client.post("/api/chat", json={"session_id": "x", "message": ""}).status_code == 422
