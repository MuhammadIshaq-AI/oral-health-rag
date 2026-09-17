"""Vector stores (Qdrant primary, FAISS dev fallback) and the chunk catalogue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import numpy as np

from app.rag.types import Chunk


def collection_name(corpus_version: str) -> str:
    """Qdrant collection name for a corpus version."""
    return f"dentalcare_{corpus_version[:12]}"


class VectorStore(Protocol):
    """Minimal dense-search interface."""

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        """Return top-k (chunk_id, cosine similarity)."""
        ...


def load_chunks(index_dir: Path) -> list[Chunk]:
    """Read chunks.jsonl produced by ingestion."""
    path = index_dir / "chunks.jsonl"
    with path.open(encoding="utf-8") as f:
        return [Chunk.model_validate_json(line) for line in f if line.strip()]


def load_index_manifest(index_dir: Path) -> dict[str, object]:
    """Read the index manifest (corpus_version, embedding model, counts)."""
    return json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))


class FaissStore:
    """Exact inner-product FAISS index persisted next to chunks.jsonl."""

    def __init__(self, index_dir: Path) -> None:
        import faiss

        self.index = faiss.read_index(str(index_dir / "dense.faiss"))
        self.ids: list[str] = json.loads((index_dir / "dense_ids.json").read_text(encoding="utf-8"))

    @staticmethod
    def build(index_dir: Path, ids: list[str], vectors: np.ndarray) -> None:
        """Write a new FAISS index."""
        import faiss

        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors.astype(np.float32))
        faiss.write_index(index, str(index_dir / "dense.faiss"))
        (index_dir / "dense_ids.json").write_text(json.dumps(ids), encoding="utf-8")

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        """Top-k by inner product."""
        scores, idx = self.index.search(vector.reshape(1, -1).astype(np.float32), k)
        return [(self.ids[i], float(s)) for s, i in zip(scores[0], idx[0], strict=True) if i >= 0]


class QdrantStore:
    """Qdrant collection keyed by corpus version; payload carries full provenance."""

    def __init__(self, url: str, corpus_version: str) -> None:
        from qdrant_client import QdrantClient

        self.client = QdrantClient(url=url, timeout=30)
        self.collection = collection_name(corpus_version)

    @staticmethod
    def build(url: str, corpus_version: str, chunks: list[Chunk], vectors: np.ndarray) -> str:
        """(Re)create the collection for this corpus version and upsert all chunks."""
        import uuid

        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams

        client = QdrantClient(url=url, timeout=60)
        name = collection_name(corpus_version)
        if client.collection_exists(name):
            client.delete_collection(name)
        client.create_collection(
            name, vectors_config=VectorParams(size=vectors.shape[1], distance=Distance.COSINE)
        )
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.chunk_id)),
                vector=v.tolist(),
                payload=c.model_dump(),
            )
            for c, v in zip(chunks, vectors, strict=True)
        ]
        for i in range(0, len(points), 128):
            client.upsert(name, points=points[i : i + 128], wait=True)
        return name

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        """Top-k cosine similarity."""
        res = self.client.query_points(
            self.collection, query=vector.tolist(), limit=k, with_payload=["chunk_id"]
        )
        return [(p.payload["chunk_id"], float(p.score)) for p in res.points if p.payload]
