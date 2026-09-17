"""Append-only research logging to JSONL and SQLite, plus CSV export and purge."""

from __future__ import annotations

import asyncio
import csv
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from app.telemetry.schema import TurnLog

_TURNS_DDL = """
CREATE TABLE IF NOT EXISTS turns (
    turn_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    consent INTEGER NOT NULL,
    modality TEXT,
    triage_label TEXT,
    triage_severity TEXT,
    halted_by_triage INTEGER,
    retrieval_mode TEXT,
    top_score REAL,
    refused INTEGER,
    provider TEXT,
    model TEXT,
    prompt_version TEXT,
    corpus_version TEXT,
    config_hash TEXT,
    latency_total_ms REAL,
    record TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_turns_config ON turns(config_hash);
CREATE TABLE IF NOT EXISTS consents (
    session_id TEXT NOT NULL,
    consent INTEGER NOT NULL,
    ts TEXT NOT NULL
);
"""


class ResearchLogger:
    """Writes each `TurnLog` to a daily JSONL file and a SQLite table."""

    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.db_path = log_dir / "turns.db"
        self._lock = asyncio.Lock()
        self._consent: dict[str, bool] = {}

    async def init(self) -> None:
        """Create the directory and tables; reload consent decisions."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_TURNS_DDL)
            await db.commit()
            async with db.execute("SELECT session_id, consent FROM consents ORDER BY ts") as cur:
                async for sid, consent in cur:
                    self._consent[sid] = bool(consent)

    def consent_for(self, session_id: str) -> bool:
        """Consent status (default False: log metrics only)."""
        return self._consent.get(session_id, False)

    async def set_consent(self, session_id: str, consent: bool) -> None:
        """Record a consent decision."""
        self._consent[session_id] = consent
        async with self._lock, aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO consents VALUES (?, ?, ?)",
                (session_id, int(consent), datetime.now(UTC).isoformat()),
            )
            await db.commit()

    async def log_turn(self, turn: TurnLog) -> None:
        """Persist one turn (redacted according to consent)."""
        record = turn.redacted()
        line = json.dumps(record, ensure_ascii=False)
        day = turn.ts[:10].replace("-", "")
        async with self._lock:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(_append, self.log_dir / f"turns-{day}.jsonl", line)
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript(_TURNS_DDL)
                await db.execute(
                    "INSERT OR REPLACE INTO turns VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        turn.turn_id,
                        turn.session_id,
                        turn.ts,
                        int(turn.consent),
                        turn.modality,
                        turn.triage_label,
                        turn.triage_severity,
                        int(turn.halted_by_triage),
                        turn.retrieval_mode,
                        turn.top_score,
                        int(turn.refused),
                        turn.provider,
                        turn.model,
                        turn.prompt_version,
                        turn.corpus_version,
                        turn.config_hash,
                        turn.latency_ms.get("total"),
                        line,
                    ),
                )
                await db.commit()


def _append(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _flatten(record: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in record.items():
        if key == "latency_ms" and isinstance(value, dict):
            for stage, ms in value.items():
                flat[f"latency_{stage}_ms"] = ms
        elif isinstance(value, list | dict):
            flat[key] = json.dumps(value, ensure_ascii=False)
        else:
            flat[key] = value
    return flat


def export_csv(log_dir: Path, out_path: Path) -> int:
    """Export all turns from SQLite to a flat CSV. Returns the row count."""
    db_path = log_dir / "turns.db"
    if not db_path.exists():
        raise FileNotFoundError(f"No log database at {db_path}")
    db = sqlite3.connect(db_path)
    try:
        rows = [json.loads(r[0]) for r in db.execute("SELECT record FROM turns ORDER BY ts")]
    finally:
        db.close()  # the context manager only commits; an open handle blocks purge on Windows
    flat = [_flatten(r) for r in rows]
    fields = sorted({k for r in flat for k in r}, key=lambda k: (k.startswith("latency_"), k))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(flat)
    return len(flat)


def purge(data_dir: Path, log_dir: Path) -> list[str]:
    """Delete every logged artefact: turn logs, SQLite DB, exports and cached user audio."""
    removed: list[str] = []
    for target in (log_dir, data_dir / "exports", data_dir / "audio_uploads"):
        if target.exists():
            shutil.rmtree(target)
            removed.append(str(target))
    return removed
