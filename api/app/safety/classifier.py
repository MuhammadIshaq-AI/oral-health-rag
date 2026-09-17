"""Model-based triage second opinion (zero-shot JSON classification)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import get_args

from app.llm.base import LLMClient
from app.rag.prompt import load_prompt
from app.safety.labels import Label

_VALID: frozenset[str] = frozenset(get_args(Label))


@dataclass
class ModelDecision:
    """LLM triage output."""

    label: Label
    confidence: float
    evidence: str
    error: str | None = None


def _parse(text: str) -> dict[str, object]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0)) if m else {}


async def classify_model(llm: LLMClient, message: str, prompt_version: str = "v1") -> ModelDecision:
    """Ask the LLM for a triage label; on any failure return 'none' with the error recorded."""
    prompt = load_prompt("triage", prompt_version).replace("{message}", message[:2000])
    try:
        out = await llm.generate(
            [{"role": "user", "content": prompt}], temperature=0.0, max_tokens=120, json_mode=True
        )
        data = _parse(out.text)
        if "label" not in data:
            return ModelDecision("none", 0.0, "", error=f"unparseable output {out.text[:80]!r}")
        label = str(data["label"]).strip()
        if label not in _VALID:
            return ModelDecision("none", 0.0, "", error=f"invalid label {label!r}")
        return ModelDecision(
            label,  # type: ignore[arg-type]
            float(data.get("confidence", 0.0) or 0.0),
            str(data.get("evidence", ""))[:200],
        )
    except Exception as exc:  # the rules still protect the user if the model call fails
        return ModelDecision("none", 0.0, "", error=repr(exc)[:200])
