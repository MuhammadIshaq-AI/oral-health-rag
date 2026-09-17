"""Shared fixtures: a tiny in-memory corpus and a fake embedder/store (no models, no network)."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from app.rag.bm25 import tokenize
from app.rag.types import Chunk, Hit

TEXTS = {
    "healthdirect-bleeding-gums#00": (
        "Bleeding gums",
        "Bleeding gums are often a sign of gum disease (gingivitis). Brush twice a day and floss "
        "daily. See your dentist if your gums bleed for more than a few days.",
    ),
    "healthdirect-knocked-out-tooth#00": (
        "Dental injuries",
        "If an adult tooth is knocked out, hold it by the crown, rinse it briefly in milk and put "
        "it back in the socket. If you can't, store it in milk and see a dentist within 30 minutes.",
    ),
    "bhc-dry-mouth#00": (
        "Dry mouth",
        "Dry mouth happens when you don't make enough saliva. Sip water often and chew sugar-free gum.",
    ),
    "healthdirect-public-dental#00": (
        "Public dental services",
        "Public dental services are available to eligible adults with a concession card. The Child "
        "Dental Benefits Schedule helps eligible children aged 0 to 17 with basic dental services.",
    ),
    "who-oral-health#00": (
        "Oral health",
        "Oral diseases affect close to 3.5 billion people worldwide.",
    ),
}


def make_chunks() -> list[Chunk]:
    """Build the fixture corpus."""
    out = []
    for cid, (title, text) in TEXTS.items():
        sid = cid.split("#")[0]
        who = sid.startswith("who")
        out.append(
            Chunk(
                chunk_id=cid,
                source_id=sid,
                text=text,
                source_org="World Health Organization" if who else "healthdirect Australia",
                url=f"https://example.org/{sid}",
                page_title=title,
                section="",
                retrieved_at="2026-09-17T00:00:00+00:00",
                jurisdiction="INT" if who else "AU",
                secondary=who,
                corpus_version="test",
            )
        )
    return out


class HashEmbedder:
    """Hashed bag-of-words vectors: deterministic stand-in for a dense encoder."""

    dim = 256

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in tokenize(text):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts])


class MemoryStore:
    """Brute-force cosine store."""

    def __init__(self, chunks: list[Chunk], embedder: HashEmbedder) -> None:
        self.ids = [c.chunk_id for c in chunks]
        self.m = embedder.embed_documents([c.embedding_text() for c in chunks])

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        scores = self.m @ vector
        order = np.argsort(-scores)[:k]
        return [(self.ids[i], float(scores[i])) for i in order]


class OverlapReranker:
    """Scores by query-token overlap, so tests can exercise the rerank path."""

    def rerank(self, query: str, hits: list[Hit], top_k: int) -> list[Hit]:
        q = set(tokenize(query))
        for h in hits:
            d = set(tokenize(h.chunk.embedding_text()))
            h.rerank = len(q & d) / (len(q) or 1)
        return sorted(hits, key=lambda h: h.rerank or 0.0, reverse=True)[:top_k]


@pytest.fixture
def chunks() -> list[Chunk]:
    return make_chunks()


@pytest.fixture
def retriever(chunks: list[Chunk]):
    from app.rag.retriever import Retriever

    emb = HashEmbedder()
    return Retriever(
        chunks, "test", store=MemoryStore(chunks, emb), embedder=emb, reranker=OverlapReranker()
    )
