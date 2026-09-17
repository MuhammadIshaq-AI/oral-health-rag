"""Build chunks, compute the corpus version, embed, and write Qdrant/FAISS indexes."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.rag.types import Chunk
from ingest.chunk import TokenCounter, chunk_markdown
from ingest.clean import extract
from ingest.fetch import Snapshot
from ingest.manifest import Manifest

log = logging.getLogger(__name__)

CHUNK_PARAMS: dict[str, object] = {
    "min_tokens": 300,
    "max_tokens": 500,
    "overlap": 0.15,
    "chunker": "heading-token-v1",
}
MIN_CHUNK_TOKENS = 25  # drop stray fragments (menus, captions)


def build_chunks(
    snapshots: list[Snapshot], count: TokenCounter
) -> tuple[list[Chunk], dict[str, str]]:
    """Clean and chunk every snapshot. Returns (chunks, {source_id: cleaned_text_sha256})."""
    chunks: list[Chunk] = []
    content_hashes: dict[str, str] = {}
    for snap in snapshots:
        title, body = extract(snap.html(), snap.final_url)
        if len(body) < 200:
            log.warning("Too little content extracted from %s — skipping", snap.final_url)
            continue
        content_hashes[snap.source.id] = hashlib.sha256(body.encode()).hexdigest()
        drafts = [
            d
            for d in chunk_markdown(
                body,
                title,
                count,
                min_tokens=int(CHUNK_PARAMS["min_tokens"]),  # type: ignore[call-overload]
                max_tokens=int(CHUNK_PARAMS["max_tokens"]),  # type: ignore[call-overload]
                overlap=float(CHUNK_PARAMS["overlap"]),  # type: ignore[arg-type]
            )
            if d.tokens >= MIN_CHUNK_TOKENS
        ]
        for i, d in enumerate(drafts):
            chunks.append(
                Chunk(
                    chunk_id=f"{snap.source.id}#{i:02d}",
                    source_id=snap.source.id,
                    text=d.text,
                    source_org=snap.source.source_org,
                    url=snap.final_url,
                    page_title=title,
                    section=d.section,
                    retrieved_at=snap.retrieved_at,
                    jurisdiction=snap.source.jurisdiction,
                    secondary=snap.source.secondary,
                    licence=snap.source.licence,
                    tokens=d.tokens,
                )
            )
        log.info("%-55s %3d chunks", title[:55], len(drafts))
    return chunks, content_hashes


def corpus_version(manifest: Manifest, content_hashes: dict[str, str], embedding_model: str) -> str:
    """sha256 over manifest, cleaned page contents, chunker parameters and embedding model."""
    payload = {
        "manifest": [s.model_dump(mode="json") for s in manifest.enabled_sources],
        "content": dict(sorted(content_hashes.items())),
        "chunking": CHUNK_PARAMS,
        "embedding_model": embedding_model,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def write_index(
    settings: Settings,
    manifest: Manifest,
    chunks: list[Chunk],
    content_hashes: dict[str, str],
    skipped: list[dict[str, str]],
    stores: tuple[str, ...] = ("faiss", "qdrant"),
) -> dict[str, object]:
    """Embed chunks and write chunks.jsonl, FAISS and (if reachable) Qdrant. Returns the manifest."""
    from app.rag.embed import Embedder
    from app.rag.store import FaissStore, QdrantStore

    version = corpus_version(manifest, content_hashes, settings.embedding_model)
    for c in chunks:
        c.corpus_version = version

    index_dir: Path = settings.index_dir
    index_dir.mkdir(parents=True, exist_ok=True)
    with (index_dir / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(c.model_dump_json() + "\n")

    embedder = Embedder(settings.embedding_model, settings.device)
    vectors = embedder.embed_documents([c.embedding_text() for c in chunks])
    ids = [c.chunk_id for c in chunks]

    written: dict[str, str] = {}
    if "faiss" in stores:
        FaissStore.build(index_dir, ids, vectors)
        written["faiss"] = str(index_dir / "dense.faiss")
    if "qdrant" in stores:
        try:
            written["qdrant"] = QdrantStore.build(settings.qdrant_url, version, chunks, vectors)
        except Exception as exc:  # Qdrant is optional in dev; FAISS remains usable.
            log.warning("Qdrant unavailable (%s); FAISS index only", exc)

    meta: dict[str, object] = {
        "corpus_version": version,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "embedding_model": settings.embedding_model,
        "embedding_dim": int(vectors.shape[1]),
        "chunking": CHUNK_PARAMS,
        "n_chunks": len(chunks),
        "n_pages": len(content_hashes),
        "pages": content_hashes,
        "skipped": skipped,
        "stores": written,
    }
    (index_dir / "manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
