"""Download raw HTML snapshots with provenance, reusing cached snapshots unless refreshing."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ingest.manifest import Manifest, Source
from ingest.robots import PoliteClient

log = logging.getLogger(__name__)


@dataclass
class Snapshot:
    """A stored raw page."""

    source: Source
    html_path: Path
    final_url: str
    retrieved_at: str
    status: int
    sha256: str

    def html(self) -> str:
        """Raw HTML text."""
        return self.html_path.read_text(encoding="utf-8")


def _latest_snapshot(raw_dir: Path, source: Source) -> Snapshot | None:
    metas = sorted(raw_dir.glob(f"*/{source.id}.meta.json"))
    if not metas:
        return None
    meta = json.loads(metas[-1].read_text(encoding="utf-8"))
    html_path = metas[-1].with_name(f"{source.id}.html")
    if not html_path.exists() or meta.get("url") != str(source.url):
        return None
    return Snapshot(
        source, html_path, meta["final_url"], meta["retrieved_at"], meta["status"], meta["sha256"]
    )


def fetch_all(
    manifest: Manifest, raw_dir: Path, refresh: bool = False
) -> tuple[list[Snapshot], list[dict[str, str]]]:
    """Fetch every manifest source. Returns (snapshots, skipped[{id, url, reason}])."""
    client = PoliteClient(manifest.user_agent, manifest.min_delay_s)
    run_dir = raw_dir / datetime.now(UTC).strftime("%Y%m%d")
    snapshots: list[Snapshot] = []
    skipped: list[dict[str, str]] = []

    for source in manifest.enabled_sources:
        url = str(source.url)
        if not refresh and (cached := _latest_snapshot(raw_dir, source)):
            snapshots.append(cached)
            continue
        if not client.allowed(url):
            log.warning("robots.txt disallows %s — skipping", url)
            skipped.append({"id": source.id, "url": url, "reason": "robots.txt disallow"})
            continue
        try:
            resp = client.get(url)
        except RuntimeError as exc:
            skipped.append({"id": source.id, "url": url, "reason": str(exc)})
            continue
        ctype = resp.headers.get("content-type", "")
        if resp.status_code != 200 or "html" not in ctype:
            reason = f"HTTP {resp.status_code} {ctype}"
            log.warning("Skipping %s (%s)", url, reason)
            skipped.append({"id": source.id, "url": url, "reason": reason})
            continue
        run_dir.mkdir(parents=True, exist_ok=True)
        html_path = run_dir / f"{source.id}.html"
        html_path.write_text(resp.text, encoding="utf-8")
        snap = Snapshot(
            source=source,
            html_path=html_path,
            final_url=resp.url,
            retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
            status=resp.status_code,
            sha256=hashlib.sha256(resp.content).hexdigest(),
        )
        meta = {
            "id": source.id,
            "url": url,
            "final_url": snap.final_url,
            "retrieved_at": snap.retrieved_at,
            "status": snap.status,
            "sha256": snap.sha256,
            "user_agent": manifest.user_agent,
        }
        meta_path = run_dir / f"{source.id}.meta.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log.info("Fetched %s", url)
        snapshots.append(snap)
    return snapshots, skipped
