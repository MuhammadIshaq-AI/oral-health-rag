"""Dense embeddings with a local sentence-transformers model (BAAI/bge-m3 by default)."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.config import get_settings, resolve_device


class Embedder:
    """L2-normalised dense embeddings; cosine similarity == dot product."""

    def __init__(self, model_name: str, device: str = "auto") -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.device = resolve_device(device)
        self.model = SentenceTransformer(
            model_name,
            device=self.device,
            model_kwargs={"torch_dtype": "float16"} if self.device == "cuda" else {},
        )
        self.model.max_seq_length = 1024
        # e5 models need instruction prefixes; bge-m3 does not.
        self._is_e5 = "e5" in model_name.lower()

    @property
    def dim(self) -> int:
        """Embedding dimensionality."""
        return int(self.model.get_sentence_embedding_dimension())

    def embed_documents(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        """Embed passages."""
        if self._is_e5:
            texts = [f"passage: {t}" for t in texts]
        vecs = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 64,
        )
        return np.asarray(vecs, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a search query."""
        if self._is_e5:
            text = f"query: {text}"
        vec = self.model.encode([text], normalize_embeddings=True)
        return np.asarray(vec[0], dtype=np.float32)


@lru_cache
def get_embedder() -> Embedder:
    """Process-wide embedder singleton."""
    s = get_settings()
    return Embedder(s.embedding_model, s.device)
