"""Triage orchestration: rules first, optional model second opinion, most-urgent wins."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.experiments import TriageConfig
from app.llm.base import LLMClient, Timer
from app.safety.classifier import ModelDecision, classify_model
from app.safety.labels import HALTING, SEVERITY, Label, Severity, most_urgent
from app.safety.responses import TEMPLATES
from app.safety.rules import RuleDecision, classify_rules
from app.schemas import TriageOut


@dataclass
class TriageDecision:
    """Final safety decision for a user turn."""

    label: Label
    severity: Severity
    source: str  # "rules" | "model" | "rules+model" | "none"
    triggers: list[str] = field(default_factory=list)
    rule_label: Label = "none"
    model_label: Label | None = None
    model_confidence: float | None = None
    model_evidence: str | None = None
    model_error: str | None = None
    latency_ms: float = 0.0

    @property
    def halts(self) -> bool:
        """True if the dental RAG flow must not run."""
        return self.label in HALTING

    def to_out(self) -> TriageOut:
        """API representation."""
        t = TEMPLATES[self.label]
        return TriageOut(
            label=self.label,
            severity=self.severity,
            title=t.title or None,
            message=t.message or None,
            actions=t.actions,
            halted=self.halts,
        )


async def triage(
    message: str, cfg: TriageConfig, llm: LLMClient | None, prompt_version: str = "v1"
) -> TriageDecision:
    """Classify one user message. The model can escalate but never downgrade a rule decision."""
    with Timer() as t:
        rules = classify_rules(message)
        model = None
        if cfg.use_model and llm is not None:
            model = await classify_model(llm, message, prompt_version)
    return combine(rules, model, t.ms)


def combine(rules: RuleDecision, model: ModelDecision | None, latency_ms: float) -> TriageDecision:
    """Merge rule and model decisions: most urgent label wins."""
    label: Label = rules.label
    source = "rules" if rules.label != "none" else "none"
    if model is not None and model.error is None:
        label = most_urgent(rules.label, model.label)
        if model.label == label and rules.label == label and label != "none":
            source = "rules+model"
        elif model.label == label and label != "none":
            source = "model"
    return TriageDecision(
        label=label,
        severity=SEVERITY[label],
        source=source,
        triggers=rules.triggers if rules.label == label else [],
        rule_label=rules.label,
        model_label=model.label if model else None,
        model_confidence=model.confidence if model else None,
        model_evidence=model.evidence if model else None,
        model_error=model.error if model else None,
        latency_ms=latency_ms,
    )
