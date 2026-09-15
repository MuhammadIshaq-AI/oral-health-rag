"""Embed the knowledge base with Gemini and export it for the Vercel app.

Reads data/chunks.jsonl (produced by scripts/build_index.py) and writes web/src/data/knowledge.json,
which the Next.js API route searches at request time. Run it whenever the sources change:

    python scripts/build_index.py
    python scripts/export_web_index.py
"""

import base64
import json
import math
import os
import struct
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import config  # noqa: E402  (loads .env)
from rag.store import load_chunks  # noqa: E402

# Must match EMBED_MODEL used by the web app (read from the exported file, so it stays in sync).
MODEL = os.getenv("WEB_EMBED_MODEL", "gemini-embedding-001")
DIMS = 768
BATCH = 100
OUT = config.ROOT / "web" / "src" / "data" / "knowledge.json"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:batchEmbedContents"
FIELDS = ("id", "text", "title", "section", "url", "publisher", "license")


def embed_documents(chunks: list[dict], key: str) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), BATCH):
        batch = chunks[start : start + BATCH]
        body = {
            "requests": [
                {
                    "model": f"models/{MODEL}",
                    "content": {"parts": [{"text": c["text"]}]},
                    "taskType": "RETRIEVAL_DOCUMENT",
                    "title": c["title"],
                    "outputDimensionality": DIMS,
                }
                for c in batch
            ]
        }
        for attempt in range(5):
            resp = requests.post(URL, headers={"x-goog-api-key": key}, json=body, timeout=120)
            if resp.status_code != 429:
                break
            wait = 20 * (attempt + 1)
            print(f"rate limited, retrying in {wait}s")
            time.sleep(wait)
        if not resp.ok:
            sys.exit(f"Embedding request failed (HTTP {resp.status_code}): {resp.text[:300]}")
        vectors += [e["values"] for e in resp.json()["embeddings"]]
        print(f"embedded {len(vectors)}/{len(chunks)}")
    return vectors


def pack(vector: list[float]) -> str:
    """L2-normalise (reduced-dimension gemini-embedding-001 vectors aren't) and store as base64 float32."""
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return base64.b64encode(struct.pack(f"<{len(vector)}f", *(v / norm for v in vector))).decode()


def main() -> None:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("Set GEMINI_API_KEY in .env first.")

    chunks = load_chunks()
    vectors = embed_documents(chunks, key)
    data = {
        "model": MODEL,
        "dims": DIMS,
        "created": date.today().isoformat(),
        "chunks": [{k: c[k] for k in FIELDS} | {"embedding": pack(v)} for c, v in zip(chunks, vectors)],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(config.ROOT)} ({OUT.stat().st_size / 1e6:.2f} MB, {len(chunks)} passages)")


if __name__ == "__main__":
    main()
