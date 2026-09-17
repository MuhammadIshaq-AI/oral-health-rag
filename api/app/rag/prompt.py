"""Versioned prompt templates and message construction."""

from __future__ import annotations

from functools import lru_cache

from app.config import ROOT
from app.llm.base import Message
from app.rag.types import Hit

PROMPTS_DIR = ROOT / "prompts"

DISCLAIMER = "This is general information, not dental advice."
NO_GUIDANCE = (
    "I don't have reliable Australian guidance on that. Please talk to a dentist, "
    "or call healthdirect on 1800 022 222 for free health advice any time."
)


@lru_cache
def load_prompt(name: str, version: str) -> str:
    """Load `prompts/{name}_{version}.md`."""
    return (PROMPTS_DIR / f"{name}_{version}.md").read_text(encoding="utf-8").strip()


def format_passages(hits: list[Hit]) -> str:
    """Number passages [1]..[n] with provenance headers."""
    blocks = []
    for i, h in enumerate(hits, start=1):
        c = h.chunk
        where = f"{c.page_title}" + (f" — {c.section}" if c.section else "")
        tag = " (non-Australian source)" if c.secondary else ""
        blocks.append(f"[{i}] {where} | {c.source_org}{tag}\n{c.text}")
    return "\n\n".join(blocks)


def build_answer_messages(
    question: str, hits: list[Hit], history: list[Message], prompt_version: str
) -> list[Message]:
    """System prompt + recent history + a user turn carrying the numbered passages."""
    messages: list[Message] = [{"role": "system", "content": load_prompt("system", prompt_version)}]
    messages.extend(history)
    user = f"Passages:\n\n{format_passages(hits)}\n\nQuestion: {question}"
    messages.append({"role": "user", "content": user})
    return messages
