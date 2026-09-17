"""Command-line entry point: `python -m ingest.cli run|stats`."""

from __future__ import annotations

import argparse
import logging
from collections import Counter

from app.config import enable_system_tls, get_settings


def corpus_table() -> str:
    """Markdown table of pages/chunks per organisation (used by the README and reports)."""
    from app.rag.store import load_chunks

    chunks = load_chunks(get_settings().index_dir)
    by_org = Counter((c.source_org, c.jurisdiction, c.secondary) for c in chunks)
    first = {c.source_id: c for c in chunks}.values()
    pages = Counter((c.source_org, c.jurisdiction, c.secondary) for c in first)
    lines = ["| Organisation | Jurisdiction | Pages | Chunks |", "|---|---|---:|---:|"]
    for (org, jur, sec), n in sorted(by_org.items(), key=lambda kv: (kv[0][2], kv[0][0])):
        label = f"{org} (secondary, non-Australian)" if sec else org
        lines.append(f"| {label} | {jur} | {pages[(org, jur, sec)]} | {n} |")
    lines.append(f"| **Total** | | **{len(first)}** | **{len(chunks)}** |")
    return "\n".join(lines)


def _stats() -> None:
    from app.rag.store import load_chunks, load_index_manifest

    s = get_settings()
    chunks = load_chunks(s.index_dir)
    meta = load_index_manifest(s.index_dir)
    print(f"corpus_version: {meta['corpus_version']}")
    print(f"embedding_model: {meta['embedding_model']}  stores: {meta['stores']}")
    print(f"pages: {meta['n_pages']}  chunks: {len(chunks)}  skipped: {len(meta['skipped'])}\n")  # type: ignore[arg-type]
    print(corpus_table())
    toks = sorted(c.tokens for c in chunks)
    if toks:
        print(f"\ntokens/chunk: min {toks[0]}  median {toks[len(toks) // 2]}  max {toks[-1]}")
        bins = Counter(min(t // 100, 6) for t in toks)
        for b in range(7):
            label = f"{b * 100}-{b * 100 + 99}" if b < 6 else "600+"
            print(f"  {label:>8} {'#' * (bins[b] // 2)} {bins[b]}")
    for sk in meta["skipped"]:  # type: ignore[attr-defined]
        print(f"skipped: {sk['id']} ({sk['reason']})")


def _run(refresh: bool, stores: tuple[str, ...]) -> None:
    from ingest.chunk import hf_token_counter
    from ingest.fetch import fetch_all
    from ingest.index import build_chunks, write_index
    from ingest.manifest import load_manifest

    enable_system_tls()
    s = get_settings()
    manifest = load_manifest()
    snapshots, skipped = fetch_all(manifest, s.raw_dir, refresh=refresh)
    chunks, hashes = build_chunks(snapshots, hf_token_counter(s.embedding_model))
    meta = write_index(s, manifest, chunks, hashes, skipped, stores)
    version = str(meta["corpus_version"])[:12]
    print(
        f"Indexed {meta['n_chunks']} chunks from {meta['n_pages']} pages; corpus_version={version}"
    )


def main() -> None:
    """Parse args and dispatch."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="DentalCare AU corpus ingestion")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="fetch, chunk, embed and index the corpus")
    run.add_argument("--refresh", action="store_true", help="re-download pages even if cached")
    run.add_argument("--stores", default="faiss,qdrant", help="comma list: faiss,qdrant")
    sub.add_parser("stats", help="print corpus statistics")
    args = ap.parse_args()
    if args.cmd == "run":
        _run(args.refresh, tuple(args.stores.split(",")))
    else:
        _stats()


if __name__ == "__main__":
    main()
