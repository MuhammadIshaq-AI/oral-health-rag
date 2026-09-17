import csv
from pathlib import Path

from app.telemetry.logger import ResearchLogger, export_csv, purge
from app.telemetry.schema import TurnLog


def _turn(consent: bool, turn_id: str = "t1") -> TurnLog:
    return TurnLog(
        turn_id=turn_id,
        session_id="s" * 16,
        consent=consent,
        modality="voice",
        raw_input="my gums bleed",
        transcript="my gums bleed",
        whisper_confidence=0.91,
        triage_label="none",
        triage_severity="none",
        triage_source="none",
        rewritten_query="bleeding gums",
        answer="Answer [1].",
        provider="fake",
        model="fake",
        prompt_version="v1",
        corpus_version="abc",
        config_name="test",
        config_hash="123",
        app_version="0.1.0",
        latency_ms={"total": 12.5, "retrieve": 3.0},
    )


async def test_log_export_purge(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    logger = ResearchLogger(log_dir)
    await logger.init()
    await logger.log_turn(_turn(True, "a"))
    await logger.log_turn(_turn(False, "b"))

    out = tmp_path / "exports" / "turns.csv"
    assert export_csv(log_dir, out) == 2
    rows = {r["turn_id"]: r for r in csv.DictReader(out.open(encoding="utf-8"))}
    assert rows["a"]["transcript"] == "my gums bleed" and rows["a"]["latency_total_ms"] == "12.5"
    assert rows["b"]["transcript"] == ""  # redacted without consent

    removed = purge(tmp_path, log_dir)
    assert str(log_dir) in removed and not log_dir.exists() and not out.exists()


async def test_consent_persists(tmp_path: Path) -> None:
    logger = ResearchLogger(tmp_path)
    await logger.init()
    await logger.set_consent("session-123", True)
    reloaded = ResearchLogger(tmp_path)
    await reloaded.init()
    assert reloaded.consent_for("session-123") and not reloaded.consent_for("other-session")
