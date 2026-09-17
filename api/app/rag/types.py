"""Shared data types for the retrieval pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel


class Chunk(BaseModel):
    """An indexed passage with full provenance."""

    chunk_id: str
    source_id: str
    text: str
    source_org: str
    url: str
    page_title: str
    section: str
    retrieved_at: str
    jurisdiction: str
    secondary: bool = False
    licence: str = ""
    tokens: int = 0
    corpus_version: str = ""

    def embedding_text(self) -> str:
        """Text given to the embedder: title and section add useful context."""
        header = self.page_title + (f" — {self.section}" if self.section else "")
        return f"{header}\n{self.text}"


@dataclass
class Hit:
    """A retrieved chunk with every score it collected on the way through the pipeline."""

    chunk: Chunk
    dense: float | None = None
    bm25: float | None = None
    rrf: float | None = None
    rerank: float | None = None
    dense_rank: int | None = None
    bm25_rank: int | None = None
    extra: dict[str, float] = field(default_factory=dict)

    @property
    def score(self) -> float:
        """Best available score, in pipeline order: rerank > rrf > dense > bm25."""
        for value in (self.rerank, self.rrf, self.dense, self.bm25):
            if value is not None:
                return value
        return 0.0

    def log_record(self) -> dict[str, object]:
        """Compact dict for research logs."""
        return {
            "chunk_id": self.chunk.chunk_id,
            "url": self.chunk.url,
            "dense": _r(self.dense),
            "bm25": _r(self.bm25),
            "rrf": _r(self.rrf),
            "rerank": _r(self.rerank),
        }


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 5)
