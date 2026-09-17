"""A/B experiment configuration.

An experiment config is a YAML file under `configs/` that fully determines the
behaviour of a turn: retrieval mode, top-k values, confidence thresholds, LLM
provider/model, prompt version and triage options. Configs may `extends:` a
parent file. The canonical JSON of the *resolved* config is hashed
(`config_hash`) and written to every turn log and evaluation report, so any
result can be traced back to the exact settings that produced it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from app.config import ROOT

RetrievalMode = Literal["dense", "hybrid", "rerank"]


class LLMConfig(BaseModel):
    """Which language model to call and how."""

    provider: Literal["ollama", "openai_compat", "gemini", "openai", "anthropic", "fake"] = "ollama"
    model: str = "qwen2.5:7b-instruct"
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int = 700
    seed: int | None = 42
    timeout_s: float = 120.0


class RetrievalConfig(BaseModel):
    """Retrieval pipeline knobs."""

    mode: RetrievalMode = "rerank"
    dense_k: int = 50
    bm25_k: int = 50
    rrf_k: int = 60
    rerank_candidates: int = 30
    final_k: int = 6
    # Confidence gate: below these, the assistant declines instead of answering.
    min_rerank_score: float = 0.15
    min_dense_score: float = 0.45
    min_rrf_score: float = 0.0
    include_secondary: bool = True  # WHO (non-Australian) sources


class TriageConfig(BaseModel):
    """Safety layer options."""

    use_model: bool = True  # LLM second opinion on top of deterministic rules
    corpus_first_aid: bool = True  # use retrieved passages for trauma first-aid answers


class ExperimentConfig(BaseModel):
    """Resolved experiment configuration."""

    name: str = "default"
    description: str = ""
    prompt_version: str = "v1"
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    judge_llm: LLMConfig | None = None  # eval judge; defaults to `llm`
    triage: TriageConfig = Field(default_factory=TriageConfig)
    rewrite_queries: bool = True
    max_history_turns: int = 6

    @property
    def config_hash(self) -> str:
        """Short, stable hash of the resolved configuration."""
        return config_hash(self.model_dump(mode="json"))


def config_hash(data: dict[str, Any]) -> str:
    """sha256 of canonical JSON, truncated to 12 hex chars."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _load_raw(path: Path, seen: set[Path]) -> dict[str, Any]:
    path = path if path.is_absolute() else ROOT / path
    path = path.resolve()
    if path in seen:
        raise ValueError(f"Circular 'extends' in experiment config: {path}")
    seen.add(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    parent = data.pop("extends", None)
    if parent:
        parent_path = (path.parent / parent).resolve()
        data = _deep_merge(_load_raw(parent_path, seen), data)
    return data


def load_experiment(path: str | Path) -> ExperimentConfig:
    """Load a YAML experiment config (following `extends:` chains) and validate it."""
    return ExperimentConfig.model_validate(_load_raw(Path(path), set()))
