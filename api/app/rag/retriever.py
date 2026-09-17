"""Dense, hybrid (BM25 + dense with RRF) and reranked retrieval."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.experiments import RetrievalConfig
from app.llm.base import Timer
from app.rag.bm25 import BM25Index
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.store import FaissStore, QdrantStore, VectorStore, load_chunks, load_index_manifest
from app.rag.types import Chunk, Hit

log = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Final hits plus diagnostics for logging."""

    hits: list[Hit]
    confident: bool
    top_score: float
    latency_ms: dict[str, float] = field(default_factory=dict)


class Retriever:
    """Loads the corpus once and serves queries in any retrieval mode."""

    def __init__(
        self,
        chunks: list[Chunk],
        corpus_version: str,
        store: VectorStore | None = None,
        embedder: object | None = None,
        reranker: object | None = None,
    ) -> None:
        self.chunks = {c.chunk_id: c for c in chunks}
        self.corpus_version = corpus_version
        self.bm25 = BM25Index(list(self.chunks), [c.embedding_text() for c in chunks])
        self._store = store
        self._embedder = embedder
        self._reranker = reranker

    @classmethod
    def from_settings(cls, settings: Settings) -> Retriever:
        """Build from the on-disk index, preferring Qdrant and falling back to FAISS."""
        index_dir: Path = settings.index_dir
        chunks = load_chunks(index_dir)
        version = str(load_index_manifest(index_dir)["corpus_version"])
        store: VectorStore
        if settings.vector_store == "qdrant":
            try:
                q = QdrantStore(settings.qdrant_url, version)
                if not q.client.collection_exists(q.collection):
                    raise RuntimeError(f"collection {q.collection} missing")
                store = q
            except Exception as exc:
                log.warning("Qdrant unavailable (%s); using FAISS fallback", exc)
                store = FaissStore(index_dir)
        else:
            store = FaissStore(index_dir)
        return cls(chunks, version, store)

    @property
    def store_name(self) -> str:
        """'qdrant' or 'faiss'."""
        return "qdrant" if isinstance(self._store, QdrantStore) else "faiss"

    @property
    def embedder(self):
        """Lazily loaded dense embedder."""
        if self._embedder is None:
            from app.rag.embed import get_embedder

            self._embedder = get_embedder()
        return self._embedder

    @property
    def reranker(self):
        """Lazily loaded cross-encoder."""
        if self._reranker is None:
            from app.rag.rerank import get_reranker

            self._reranker = get_reranker()
        return self._reranker

    def _allowed(self, chunk_id: str, cfg: RetrievalConfig) -> bool:
        return chunk_id in self.chunks and (
            cfg.include_secondary or not self.chunks[chunk_id].secondary
        )

    def dense(self, query: str, k: int, cfg: RetrievalConfig) -> list[Hit]:
        """Dense top-k."""
        if self._store is None:
            raise RuntimeError("No vector store configured")
        vec = self.embedder.embed_query(query)
        results = [
            (cid, s) for cid, s in self._store.search(vec, k * 2) if self._allowed(cid, cfg)
        ][:k]
        return [
            Hit(self.chunks[cid], dense=s, dense_rank=r) for r, (cid, s) in enumerate(results, 1)
        ]

    def sparse(self, query: str, k: int, cfg: RetrievalConfig) -> list[Hit]:
        """BM25 top-k."""
        results = [
            (cid, s) for cid, s in self.bm25.search(query, k * 2) if self._allowed(cid, cfg)
        ][:k]
        return [Hit(self.chunks[cid], bm25=s, bm25_rank=r) for r, (cid, s) in enumerate(results, 1)]

    def retrieve(self, query: str, cfg: RetrievalConfig) -> RetrievalResult:
        """Run the configured retrieval mode and apply the confidence gate."""
        timings: dict[str, float] = {}
        with Timer() as t:
            dense_hits = self.dense(query, cfg.dense_k, cfg)
        timings["dense"] = t.ms

        if cfg.mode == "dense":
            hits = dense_hits[: cfg.final_k]
            top = hits[0].dense or 0.0 if hits else 0.0
            return RetrievalResult(hits, bool(hits) and top >= cfg.min_dense_score, top, timings)

        with Timer() as t:
            sparse_hits = self.sparse(query, cfg.bm25_k, cfg)
            by_id: dict[str, Hit] = {h.chunk.chunk_id: h for h in dense_hits}
            for h in sparse_hits:
                if h.chunk.chunk_id in by_id:
                    by_id[h.chunk.chunk_id].bm25 = h.bm25
                    by_id[h.chunk.chunk_id].bm25_rank = h.bm25_rank
                else:
                    by_id[h.chunk.chunk_id] = h
            fused = reciprocal_rank_fusion(
                [[h.chunk.chunk_id for h in dense_hits], [h.chunk.chunk_id for h in sparse_hits]],
                k=cfg.rrf_k,
            )
            ranked: list[Hit] = []
            for cid, score in fused:
                by_id[cid].rrf = score
                ranked.append(by_id[cid])
        timings["bm25_fusion"] = t.ms

        best_dense = max((h.dense or 0.0 for h in dense_hits), default=0.0)
        if cfg.mode == "hybrid":
            hits = ranked[: cfg.final_k]
            return RetrievalResult(
                hits, bool(hits) and best_dense >= cfg.min_dense_score, best_dense, timings
            )

        with Timer() as t:
            hits = self.reranker.rerank(query, ranked[: cfg.rerank_candidates], cfg.final_k)
        timings["rerank"] = t.ms
        top = hits[0].rerank or 0.0 if hits else 0.0
        return RetrievalResult(hits, bool(hits) and top >= cfg.min_rerank_score, top, timings)
