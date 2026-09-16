"""Free-tier chat models behind OpenAI-compatible endpoints."""

import os

from langchain_openai import ChatOpenAI

from . import config  # noqa: F401  (loads .env)

PROVIDERS = {
    # Google AI Studio free tier: https://aistudio.google.com/apikey
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        # gemini-2.5-flash is no longer offered to new API users; 3.6 Flash is Google's replacement.
        "model": "gemini-3.6-flash",
        # Flash models "think" by default, and thinking tokens count against max_tokens. Grounded
        # answering over supplied excerpts doesn't need it, and disabling it is faster and cheaper.
        "extra": {"reasoning_effort": "none"},
    },
    # Free tier, no card: https://console.groq.com
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
    },
    # Hugging Face Inference Providers router (small monthly free credit)
    "hf": {
        "base_url": "https://router.huggingface.co/v1",
        "key_env": "HF_TOKEN",
        "model": "Qwen/Qwen2.5-7B-Instruct",
    },
    # OpenRouter ":free" model variants
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    # Fully local: `ollama pull llama3.1:8b`
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "key_env": None,
        "model": "llama3.1:8b",
    },
}


def get_llm(provider: str | None = None, model: str | None = None, temperature: float = 0.1) -> ChatOpenAI:
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Choose from: {', '.join(PROVIDERS)}")
    cfg = PROVIDERS[provider]

    api_key = os.getenv(cfg["key_env"]) if cfg["key_env"] else "ollama"
    if not api_key:
        raise RuntimeError(f"Set {cfg['key_env']} to use the '{provider}' provider (see .env.example).")

    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=api_key,
        model=model or os.getenv("LLM_MODEL") or cfg["model"],
        temperature=temperature,
        max_tokens=1024,
        max_retries=6,  # free tiers rate-limit; the client backs off on 429s
        timeout=90,
        **cfg.get("extra", {}),
    )
