"""Process-level settings loaded from environment variables / `.env`.

Anything that changes *experimental behaviour* (retrieval mode, model, prompt
version, thresholds) lives in the YAML experiment config instead — see
`app.experiments` — so that it is hashed and logged with every turn.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment configuration for the API, ingestion and evaluation."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    experiment_config: Path = ROOT / "configs" / "default.yaml"

    # LLM providers
    ollama_base_url: str = "http://localhost:11434"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Retrieval
    vector_store: str = "qdrant"  # qdrant | faiss
    qdrant_url: str = "http://localhost:6333"
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    device: str = "auto"

    # Speech
    whisper_model: str = "small"
    whisper_compute_type: str = "auto"
    tts_enabled: bool = True
    piper_voice: str = "en_GB-alba-medium"

    # Storage
    data_dir: Path = ROOT / "data"
    log_dir: Path = ROOT / "data" / "logs"

    # API
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def index_dir(self) -> Path:
        """Directory holding chunks.jsonl, BM25 and FAISS artefacts and the index manifest."""
        return self.data_dir / "index"

    @property
    def raw_dir(self) -> Path:
        """Directory holding raw HTML snapshots."""
        return self.data_dir / "raw"

    @property
    def models_dir(self) -> Path:
        """Directory for locally downloaded models (Piper voices etc.)."""
        return self.data_dir / "models"

    def resolve(self, p: Path) -> Path:
        """Resolve a possibly-relative path against the repository root."""
        return p if p.is_absolute() else ROOT / p


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    s = Settings()
    s.experiment_config = s.resolve(s.experiment_config)
    s.data_dir = s.resolve(s.data_dir)
    s.log_dir = s.resolve(s.log_dir)
    return s


def resolve_device(pref: str = "auto") -> str:
    """Pick 'cuda' when available (and requested/auto), else 'cpu'."""
    if pref != "auto":
        return pref
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def enable_system_tls() -> None:
    """Use the OS certificate store for outbound HTTPS (needed behind TLS-inspecting proxies)."""
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass
