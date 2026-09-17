"""Heading-aware, token-budgeted chunking.

Algorithm
---------
1. Split the markdown into sections at `#`-`###` headings, keeping the heading
   path (e.g. "Causes > Gum disease").
2. Split each section into blocks (paragraphs, list items, table rows). Blocks
   longer than the max budget are split at sentence boundaries.
3. Greedily pack blocks into chunks of `min_tokens`–`max_tokens`. A chunk is only
   closed at a section boundary once it has reached `min_tokens`, so tiny
   sections are merged with their neighbours rather than becoming orphan chunks.
4. Each new chunk starts with trailing blocks/sentences from the previous one
   amounting to about `overlap` × previous-chunk tokens.

Token counts use the embedding model's tokenizer (bge-m3 by default) so that
budgets match what the encoder actually sees.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

TokenCounter = Callable[[str], int]

_HEADING = re.compile(r"^(#{1,3})\s+(.*\S)\s*$")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass
class Block:
    """A paragraph-like unit of text with its heading path."""

    text: str
    section: str
    tokens: int


@dataclass
class ChunkDraft:
    """A chunk before provenance metadata is attached."""

    text: str
    sections: list[str] = field(default_factory=list)
    tokens: int = 0

    @property
    def section(self) -> str:
        """Primary (first non-empty) section label for the chunk."""
        return next((s for s in self.sections if s), "")


def whitespace_token_counter(text: str) -> int:
    """Cheap approximation (~1.3 subword tokens per word) used when no tokenizer is loaded."""
    return int(len(text.split()) * 1.3) + 1


def hf_token_counter(model_name: str = "BAAI/bge-m3") -> TokenCounter:
    """Token counter backed by a Hugging Face tokenizer."""
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_name)

    def count(text: str) -> int:
        return len(tok.encode(text, add_special_tokens=False))

    return count


def _sections(markdown: str, page_title: str) -> list[tuple[str, str]]:
    """Return [(heading_path, body_text)] in document order."""
    path: list[str] = []
    current: list[str] = []
    out: list[tuple[str, str]] = []

    def flush() -> None:
        body = "\n".join(current).strip()
        if body:
            out.append((" > ".join(path), body))
        current.clear()

    for line in markdown.splitlines():
        m = _HEADING.match(line)
        if m:
            flush()
            level, heading = len(m.group(1)), m.group(2).strip("*_ ").strip()
            if level == 1 and heading.lower() == page_title.lower():
                path = []
                continue
            path = path[: level - 1] if level > 1 else []
            path.append(heading)
        else:
            current.append(line)
    flush()
    return out


def _blocks(section: str, body: str, count: TokenCounter, max_tokens: int) -> list[Block]:
    raw = [b.strip() for b in re.split(r"\n\s*\n|\n(?=\s*[-*+] |\s*\d+\. |\|)", body)]
    blocks: list[Block] = []
    for text in filter(None, raw):
        n = count(text)
        if n <= max_tokens:
            blocks.append(Block(text, section, n))
            continue
        for sentence in filter(None, (s.strip() for s in _SENTENCE.split(text))):
            blocks.append(Block(sentence, section, count(sentence)))
    return blocks


def chunk_markdown(
    markdown: str,
    page_title: str,
    count: TokenCounter = whitespace_token_counter,
    min_tokens: int = 300,
    max_tokens: int = 500,
    overlap: float = 0.15,
) -> list[ChunkDraft]:
    """Split a markdown page into overlapping, heading-aware chunks."""
    blocks: list[Block] = []
    for section, body in _sections(markdown, page_title):
        blocks.extend(_blocks(section, body, count, max_tokens))
    if not blocks:
        return []

    chunks: list[ChunkDraft] = []
    current: list[Block] = []

    def cur_tokens() -> int:
        return sum(b.tokens for b in current)

    def emit() -> None:
        nonlocal current
        if not current:
            return
        chunks.append(_render(current))
        # Carry trailing blocks as overlap into the next chunk.
        budget = int(overlap * cur_tokens())
        carry: list[Block] = []
        for b in reversed(current):
            if sum(c.tokens for c in carry) + b.tokens > budget:
                break
            carry.insert(0, b)
        if not carry and budget > 0:
            # No whole block fits: carry the last sentences of the final block instead.
            sentences = _SENTENCE.split(current[-1].text)
            tail: list[str] = []
            for s in reversed(sentences):
                if count(" ".join([s, *tail])) > budget:
                    break
                tail.insert(0, s)
            if not tail or len(tail) == len(sentences):
                # Single long sentence: fall back to trailing words.
                words = current[-1].text.split()
                keep = max(1, int(len(words) * budget / max(current[-1].tokens, 1)))
                tail = words[-keep:] if keep < len(words) else []
            if tail:
                text = " ".join(tail)
                carry = [Block(text, current[-1].section, count(text))]
        current = carry

    for i, block in enumerate(blocks):
        new_section = i > 0 and block.section != blocks[i - 1].section
        if current and (
            cur_tokens() + block.tokens > max_tokens or (new_section and cur_tokens() >= min_tokens)
        ):
            emit()
        current.append(block)
    if current:
        overlap_only = chunks and all(b.text in chunks[-1].text for b in current)
        if not overlap_only:
            tail = _render(current)
            if (
                chunks
                and tail.tokens < min_tokens // 3
                and chunks[-1].tokens + tail.tokens <= max_tokens
            ):
                prev = chunks.pop()
                merged_text = prev.text + "\n\n" + tail.text
                chunks.append(
                    ChunkDraft(merged_text, prev.sections + tail.sections, count(merged_text))
                )
            else:
                chunks.append(tail)
    return chunks


def _render(blocks: list[Block]) -> ChunkDraft:
    parts: list[str] = []
    sections: list[str] = []
    last_section: str | None = None
    for b in blocks:
        if b.section != last_section:
            if b.section:
                parts.append(f"## {b.section.split(' > ')[-1]}")
            sections.append(b.section)
            last_section = b.section
        parts.append(b.text)
    text = "\n\n".join(parts)
    return ChunkDraft(text=text, sections=sections, tokens=sum(b.tokens for b in blocks))
