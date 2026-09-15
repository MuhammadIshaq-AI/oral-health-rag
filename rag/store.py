"""Local embeddings + FAISS vector store."""

import json

from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from . import config


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=config.EMBED_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
        query_encode_kwargs={"normalize_embeddings": True, "prompt": config.BGE_QUERY_PREFIX},
    )


def build_store(chunks: list[dict]) -> FAISS:
    docs = [
        Document(
            # Prepend the page title so chunks like "Treatment" keep their topic when embedded.
            page_content=f"{c['title']}\n{c['text']}",
            metadata={k: v for k, v in c.items() if k != "text"} | {"text": c["text"]},
        )
        for c in chunks
    ]
    store = FAISS.from_documents(
        docs, get_embeddings(), distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT
    )
    store.save_local(str(config.INDEX_DIR))
    return store


def load_store() -> FAISS:
    if not (config.INDEX_DIR / "index.faiss").exists():
        raise FileNotFoundError("No index found. Run `python scripts/build_index.py` first.")
    # The index is produced locally by build_index.py, so pickle deserialisation is trusted.
    return FAISS.load_local(
        str(config.INDEX_DIR),
        get_embeddings(),
        allow_dangerous_deserialization=True,
        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT,
    )


def load_chunks() -> list[dict]:
    with config.CHUNKS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]
