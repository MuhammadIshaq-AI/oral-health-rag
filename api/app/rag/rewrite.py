"""Conversational query rewriting (resolves follow-ups before retrieval)."""

from __future__ import annotations

from app.llm.base import LLMClient, Message
from app.rag.prompt import load_prompt


def format_history(history: list[Message], max_chars: int = 600) -> str:
    """Render prior turns compactly for the rewrite prompt."""
    lines = []
    for m in history:
        if m["role"] == "system":
            continue
        content = m["content"].replace("\n", " ")
        if len(content) > max_chars:
            content = content[:max_chars] + "…"
        lines.append(f"{m['role'].capitalize()}: {content}")
    return "\n".join(lines)


async def rewrite_query(
    llm: LLMClient, question: str, history: list[Message], prompt_version: str
) -> str:
    """Return a standalone query; the original question if there is no history or the call fails."""
    if not any(m["role"] == "user" for m in history):
        return question
    prompt = load_prompt("rewrite", prompt_version).format(
        history=format_history(history), question=question
    )
    try:
        result = await llm.generate(
            [{"role": "user", "content": prompt}], temperature=0.0, max_tokens=80
        )
    except Exception:
        return question
    text = result.text.strip().strip('"').splitlines()[0].strip() if result.text.strip() else ""
    return text if 3 <= len(text) <= 300 else question
