"""LLM provider implementations: Ollama, OpenAI-compatible (Gemini/OpenAI/vLLM), Anthropic, fake."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.base import LLMError, LLMResult, Message, Timer

_RETRY_STATUS = {408, 429, 500, 502, 503, 504}


async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    retries: int = 5,
) -> dict[str, Any]:
    delay = 2.0
    last = ""
    for attempt in range(retries):
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code not in _RETRY_STATUS:
                if resp.status_code >= 400:
                    raise LLMError(f"{url} → HTTP {resp.status_code}: {resp.text[:300]}")
                return resp.json()
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
            retry_after = resp.headers.get("retry-after")
            if retry_after and retry_after.isdigit():
                delay = max(delay, float(retry_after))
            else:
                m = re.search(r'"retryDelay":\s*"(\d+)s"', resp.text)
                if m:
                    delay = max(delay, float(m.group(1)) + 1)
        except httpx.HTTPError as exc:
            last = repr(exc)
        if attempt < retries - 1:
            await asyncio.sleep(min(delay, 90))
            delay *= 2
    raise LLMError(f"{url} failed after {retries} attempts: {last}")


class OllamaClient:
    """Local open-weight models served by Ollama (native /api/chat)."""

    provider = "ollama"

    def __init__(
        self, model: str, base_url: str, seed: int | None = 42, timeout_s: float = 300
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.seed = seed
        self._http = httpx.AsyncClient(timeout=timeout_s)

    def _payload(
        self, messages: list[Message], temperature: float, max_tokens: int
    ) -> dict[str, Any]:
        options: dict[str, Any] = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": 8192,
        }
        if self.seed is not None:
            options["seed"] = self.seed
        return {"model": self.model, "messages": messages, "options": options}

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 700,
        json_mode: bool = False,
    ) -> LLMResult:
        """Non-streaming chat completion."""
        payload = self._payload(messages, temperature, max_tokens) | {"stream": False}
        if json_mode:
            payload["format"] = "json"
        with Timer() as t:
            data = await _post_with_retry(self._http, f"{self.base_url}/api/chat", payload, {})
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
        }
        return LLMResult(data["message"]["content"], self.model, self.provider, t.ms, usage)

    async def stream(
        self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 700
    ) -> AsyncIterator[str]:
        """Streaming chat completion."""
        payload = self._payload(messages, temperature, max_tokens) | {"stream": True}
        async with self._http.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
            async for line in resp.aiter_lines():
                if line:
                    delta = json.loads(line).get("message", {}).get("content", "")
                    if delta:
                        yield delta


class OpenAICompatClient:
    """Any OpenAI-compatible /chat/completions endpoint (OpenAI, Gemini, vLLM)."""

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        provider: str = "openai_compat",
        seed: int | None = None,
        timeout_s: float = 120,
    ) -> None:
        if not api_key:
            raise LLMError(f"No API key configured for provider '{provider}'")
        self.model = model
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.seed = seed
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._http = httpx.AsyncClient(timeout=timeout_s)

    def _payload(
        self, messages: list[Message], temperature: float, max_tokens: int
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        if self.provider == "gemini":
            payload["reasoning_effort"] = "none"  # deterministic, low-latency answers
        return payload

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 700,
        json_mode: bool = False,
    ) -> LLMResult:
        """Non-streaming chat completion."""
        payload = self._payload(messages, temperature, max_tokens)
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        with Timer() as t:
            data = await _post_with_retry(
                self._http, f"{self.base_url}/chat/completions", payload, self._headers
            )
        text = (data["choices"][0]["message"].get("content") or "").strip()
        usage = {k: int(v) for k, v in (data.get("usage") or {}).items() if isinstance(v, int)}
        return LLMResult(text, self.model, self.provider, t.ms, usage)

    async def stream(
        self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 700
    ) -> AsyncIterator[str]:
        """Server-sent-events streaming."""
        payload = self._payload(messages, temperature, max_tokens) | {"stream": True}
        async with self._http.stream(
            "POST", f"{self.base_url}/chat/completions", json=payload, headers=self._headers
        ) as resp:
            if resp.status_code >= 400:
                raise LLMError(f"HTTP {resp.status_code}: {(await resp.aread())[:300]!r}")
            async for line in resp.aiter_lines():
                if not line.startswith("data: ") or line.endswith("[DONE]"):
                    continue
                choices = json.loads(line[6:]).get("choices") or [{}]
                delta = choices[0].get("delta", {}).get("content")
                if delta:
                    yield delta


class AnthropicClient:
    """Anthropic Messages API."""

    provider = "anthropic"

    def __init__(self, model: str, api_key: str, timeout_s: float = 120) -> None:
        if not api_key:
            raise LLMError("No API key configured for provider 'anthropic'")
        from anthropic import AsyncAnthropic

        self.model = model
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout_s, max_retries=5)

    @staticmethod
    def _split(messages: list[Message]) -> tuple[str, list[dict[str, str]]]:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [
            {"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"
        ]
        return system, rest

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 700,
        json_mode: bool = False,
    ) -> LLMResult:
        """Non-streaming message."""
        system, rest = self._split(messages)
        with Timer() as t:
            resp = await self._client.messages.create(
                model=self.model,
                system=system,
                messages=rest,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        usage = {
            "prompt_tokens": resp.usage.input_tokens,
            "completion_tokens": resp.usage.output_tokens,
        }
        return LLMResult(text, self.model, self.provider, t.ms, usage)

    async def stream(
        self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 700
    ) -> AsyncIterator[str]:
        """Streaming message."""
        system, rest = self._split(messages)
        async with self._client.messages.stream(
            model=self.model,
            system=system,
            messages=rest,
            temperature=temperature,
            max_tokens=max_tokens,
        ) as s:
            async for text in s.text_stream:
                yield text


class FakeClient:
    """Deterministic offline client for tests: cites passage [1] and echoes the question."""

    provider = "fake"

    def __init__(self, model: str = "fake-echo", responses: list[str] | None = None) -> None:
        self.model = model
        self.responses = list(responses or [])
        self.calls: list[list[Message]] = []

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 700,
        json_mode: bool = False,
    ) -> LLMResult:
        """Return queued responses, else a canned cited answer."""
        self.calls.append(messages)
        if self.responses:
            text = self.responses.pop(0)
        elif json_mode:
            text = '{"label": "none", "confidence": 0.5}'
        else:
            text = "Brushing twice a day with fluoride toothpaste helps protect your teeth [1]."
        return LLMResult(text, self.model, self.provider, 1.0)

    async def stream(
        self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 700
    ) -> AsyncIterator[str]:
        """Stream the generate() output word by word."""
        result = await self.generate(messages)
        for word in result.text.split(" "):
            yield word + " "
