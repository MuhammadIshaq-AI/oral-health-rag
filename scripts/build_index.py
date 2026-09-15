"""Scrape sources -> chunk -> embed -> save FAISS index to data/index."""

import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import config  # noqa: E402
from rag.ingest import build_chunks  # noqa: E402
from rag.store import build_store  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for noisy in ("httpx", "huggingface_hub", "sentence_transformers", "faiss"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    chunks = build_chunks()
    if not chunks:
        sys.exit("No chunks produced; check network access and source URLs.")
    print(f"\n{len(chunks)} chunks from {len({c['url'] for c in chunks})} pages", dict(Counter(c["publisher"] for c in chunks)))
    build_store(chunks)
    print(f"Index saved to {config.INDEX_DIR}")
