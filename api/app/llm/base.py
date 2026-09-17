"""Provider-agnostic LLM interface."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypedDict


class Message(TypedDict):
    """A chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class LLMResult:
    """Model output plus accounting."""

    text: str
    model: str
    provider: str
    latency_ms: float
    usage: dict[str, int] = field(default_factory=dict)


class LLMError(RuntimeError):
    """Raised when a provider call fails after retries."""


class LLMClient(Protocol):
    """Every provider implements this interface."""

    provider: str
    model: str

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 700,
        json_mode: bool = False,
    ) -> LLMResult:
        """Return a full completion."""
        ...

    def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 700,
    ) -> AsyncIterator[str]:
        """Yield text deltas."""
        ...


class Timer:
    """Tiny context manager for millisecond timings."""

    def __enter__(self) -> Timer:
        self.start = time.perf_counter()
        self.ms = 0.0
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = (time.perf_counter() - self.start) * 1000
