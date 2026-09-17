"""Cross-encoder reranking (BAAI/bge-reranker-v2-m3)."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings, resolve_device
from app.rag.types import Hit


class Reranker:
    """Scores (query, passage) pairs jointly; outputs sigmoid relevance in [0, 1]."""

    def __init__(self, model_name: str, device: str = "auto") -> None:
        from sentence_transformers import CrossEncoder

        self.model_name = model_name
        dev = resolve_device(device)
        self.model = CrossEncoder(
            model_name,
            device=dev,
            max_length=1024,
            model_kwargs={"torch_dtype": "float16"} if dev == "cuda" else {},
        )

    def rerank(self, query: str, hits: list[Hit], top_k: int) -> list[Hit]:
        """Attach `rerank` scores and return the top_k hits by that score."""
        if not hits:
            return []
        import torch

        pairs = [(query, h.chunk.embedding_text()) for h in hits]
        scores = self.model.predict(pairs, batch_size=8, activation_fn=torch.nn.Sigmoid())
        for hit, score in zip(hits, scores, strict=True):
            hit.rerank = float(score)
        return sorted(hits, key=lambda h: h.rerank or 0.0, reverse=True)[:top_k]


@lru_cache
def get_reranker() -> Reranker:
    """Process-wide reranker singleton."""
    s = get_settings()
    return Reranker(s.reranker_model, s.device)
