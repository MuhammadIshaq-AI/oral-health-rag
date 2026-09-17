"""Construct an LLM client from an experiment config."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.experiments import LLMConfig
from app.llm.base import LLMClient
from app.llm.providers import AnthropicClient, FakeClient, OllamaClient, OpenAICompatClient

GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
OPENAI_BASE = "https://api.openai.com/v1"

#: Providers that send data off the local machine (surfaced in /api/health and the UI).
REMOTE_PROVIDERS = frozenset({"gemini", "openai", "anthropic", "openai_compat"})


def make_llm(cfg: LLMConfig, settings: Settings | None = None) -> LLMClient:
    """Return a client for `cfg.provider`."""
    s = settings or get_settings()
    match cfg.provider:
        case "ollama":
            return OllamaClient(
                cfg.model, cfg.base_url or s.ollama_base_url, cfg.seed, cfg.timeout_s
            )
        case "gemini":
            return OpenAICompatClient(
                cfg.model,
                cfg.base_url or GEMINI_OPENAI_BASE,
                s.gemini_api_key,
                "gemini",
                None,
                cfg.timeout_s,
            )
        case "openai":
            return OpenAICompatClient(
                cfg.model,
                cfg.base_url or OPENAI_BASE,
                s.openai_api_key,
                "openai",
                cfg.seed,
                cfg.timeout_s,
            )
        case "openai_compat":  # e.g. a local vLLM server
            if not cfg.base_url:
                raise ValueError("openai_compat provider needs llm.base_url")
            return OpenAICompatClient(
                cfg.model, cfg.base_url, "local", "openai_compat", cfg.seed, cfg.timeout_s
            )
        case "anthropic":
            return AnthropicClient(cfg.model, s.anthropic_api_key, cfg.timeout_s)
        case "fake":
            return FakeClient(cfg.model)
    raise ValueError(f"Unknown LLM provider: {cfg.provider}")


def is_local(cfg: LLMConfig) -> bool:
    """True if the provider keeps data on this machine."""
    if cfg.provider == "openai_compat":
        return bool(cfg.base_url and ("localhost" in cfg.base_url or "127.0.0.1" in cfg.base_url))
    return cfg.provider not in REMOTE_PROVIDERS
