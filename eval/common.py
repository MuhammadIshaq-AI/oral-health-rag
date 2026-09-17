"""Shared evaluation utilities: data loading, cached LLM calls, text helpers."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.config import ROOT
from app.llm.base import LLMClient, LLMResult, Message

EVAL_DIR = ROOT / "eval"
CACHE_DIR = EVAL_DIR / ".cache"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file (blank lines ignored)."""
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def gold_questions(include_todo: bool = False) -> list[dict[str, Any]]:
    """Gold retrieval items that have relevance labels (status seed/validated)."""
    items = read_jsonl(EVAL_DIR / "gold_retrieval.jsonl")
    return [g for g in items if include_todo or (g["status"] != "todo" and g["relevant_urls"])]


def extra_questions() -> list[dict[str, Any]]:
    """Unanswerable / unsafe / out-of-scope probes for refusal behaviour."""
    return read_jsonl(EVAL_DIR / "questions_extra.jsonl")


def git_commit() -> str:
    """Short git commit of the working tree (with '+dirty' if modified)."""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
        dirty = subprocess.run(["git", "diff", "--quiet"], cwd=ROOT).returncode != 0
        return sha + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


class CachedLLM:
    """Disk cache around an LLM client so evaluation runs are resumable and cheap to re-run.

    The cache key covers provider, model, messages and decoding parameters; a changed
    prompt or config therefore never reuses a stale answer.
    """

    def __init__(self, inner: LLMClient, namespace: str) -> None:
        self.inner = inner
        self.provider = inner.provider
        self.model = inner.model
        self.dir = CACHE_DIR / "llm" / namespace
        self.dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _key(self, messages: list[Message], **params: Any) -> Path:
        blob = json.dumps(
            {"p": self.provider, "m": self.model, "msg": messages, **params}, sort_keys=True
        )
        return self.dir / f"{hashlib.sha256(blob.encode()).hexdigest()[:32]}.json"

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 700,
        json_mode: bool = False,
    ) -> LLMResult:
        """Cached generate()."""
        path = self._key(messages, t=temperature, n=max_tokens, j=json_mode)
        if path.exists():
            self.hits += 1
            return LLMResult(**json.loads(path.read_text(encoding="utf-8")))
        self.misses += 1
        result = await self.inner.generate(
            messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode
        )
        path.write_text(json.dumps(result.__dict__), encoding="utf-8")
        return result

    def stream(
        self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 700
    ) -> AsyncIterator[str]:
        """Streaming is not cached."""
        return self.inner.stream(messages, temperature=temperature, max_tokens=max_tokens)


_CITATION = re.compile(r"\s*\[\d{1,2}\]")


def plain_text(answer: str) -> str:
    """Answer text without citations, markdown or the disclaimer (for readability metrics)."""
    from app.rag.prompt import DISCLAIMER

    text = _CITATION.sub("", answer.replace(DISCLAIMER, ""))
    text = re.sub(r"\*\*|__|`|^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return " ".join(ln if ln.endswith((".", "!", "?", ":")) else ln + "." for ln in lines)


def word_count(text: str) -> int:
    """Words in the plain-text answer."""
    return len(plain_text(text).split())


def fk_grade(text: str) -> float:
    """Flesch-Kincaid grade level of the plain-text answer."""
    import textstat

    plain = plain_text(text)
    return float(textstat.flesch_kincaid_grade(plain)) if plain else 0.0


def mean(values: list[float]) -> float | None:
    """Arithmetic mean or None for empty input."""
    return sum(values) / len(values) if values else None
