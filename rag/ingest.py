"""Download source pages, extract the main text as Markdown, and split into cited chunks."""

import hashlib
import json
import logging
import re
import time
from datetime import date

import requests
import trafilatura
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from . import config
from .sources import SOURCES

log = logging.getLogger(__name__)


def fetch(url: str, delay: float = 1.0) -> dict | None:
    """Fetch a page, caching raw HTML under data/raw so rebuilds don't re-hit the sites."""
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = config.RAW_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".json")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    try:
        resp = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=30)
    except requests.RequestException as exc:
        log.warning("Skipping %s (%s)", url, exc)
        return None
    time.sleep(delay)
    if resp.status_code != 200:
        log.warning("Skipping %s (HTTP %s)", url, resp.status_code)
        return None
    page = {"url": url, "final_url": resp.url, "retrieved": date.today().isoformat(), "html": resp.text}
    cache.write_text(json.dumps(page), encoding="utf-8")
    return page


def extract(html: str, url: str) -> tuple[str, str]:
    """Return (title, markdown body) with navigation and boilerplate removed."""
    meta = trafilatura.extract_metadata(html)
    title = (meta.title if meta and meta.title else url).strip()
    title = re.sub(r"\s*[-|–]\s*(NHS|World Health Organization.*|WHO)$", "", title)
    body = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_formatting=True,
        include_links=False,
        include_images=False,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    return title, body or ""


def chunk_page(title: str, markdown: str, source: dict, final_url: str, retrieved: str) -> list[dict]:
    header_splitter = MarkdownHeaderTextSplitter(
        [("#", "h1"), ("##", "h2"), ("###", "h3")], strip_headers=False
    )
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP
    )
    docs = char_splitter.split_documents(header_splitter.split_text(markdown))

    slug = source.get("slug") or "-".join(final_url.rstrip("/").split("/")[-2:])  # e.g. mouth-cancer-symptoms
    prefix = re.sub(r"\W+", "-", source["publisher"].lower()).strip("-")
    # Curated files have short but meaningful sections (e.g. contact details); scraped pages don't.
    min_len = 20 if "path" in source else 80
    chunks = []
    for i, doc in enumerate(docs):
        text = doc.page_content.strip()
        if len(text) < min_len:  # stray headings / footer fragments
            continue
        section = " > ".join(v for k, v in doc.metadata.items() if k.startswith("h") and v != title)
        chunks.append(
            {
                "id": f"{prefix}-{slug}-{i:03d}",
                "text": text,
                "title": title,
                "section": section,
                "url": final_url,
                "publisher": source["publisher"],
                "license": source["license"],
                "retrieved": retrieved,
            }
        )
    return chunks


def build_chunks() -> list[dict]:
    all_chunks = []
    for source in SOURCES:
        if "path" in source:  # curated local Markdown (the practice's own information)
            body = (config.ROOT / source["path"]).read_text(encoding="utf-8")
            title, final_url, retrieved = source["title"], source["url"], source["retrieved"]
        else:
            page = fetch(source["url"])
            if page is None:
                continue
            title, body = extract(page["html"], page["final_url"])
            final_url, retrieved = page["final_url"], page["retrieved"]
        if not body:
            log.warning("No main content extracted from %s", source["url"])
            continue
        chunks = chunk_page(title, body, source, final_url, retrieved)
        log.info("%-60s %3d chunks", title[:60], len(chunks))
        all_chunks.extend(chunks)

    config.CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with config.CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return all_chunks
