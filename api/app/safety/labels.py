"""Triage labels, their severity and precedence."""

from __future__ import annotations

from typing import Literal

Label = Literal[
    "crisis_self_harm",
    "emergency_airway",
    "medical_emergency_other",
    "urgent_fracture",
    "urgent_bleeding",
    "dental_trauma_avulsion",
    "urgent_swelling",
    "out_of_scope",
    "none",
]
Severity = Literal["none", "info", "urgent", "emergency", "crisis"]

#: Highest precedence first. When rules and model disagree, the earlier label wins.
PRECEDENCE: tuple[Label, ...] = (
    "crisis_self_harm",
    "emergency_airway",
    "medical_emergency_other",
    "urgent_fracture",
    "urgent_bleeding",
    "dental_trauma_avulsion",
    "urgent_swelling",
    "out_of_scope",
    "none",
)

SEVERITY: dict[Label, Severity] = {
    "crisis_self_harm": "crisis",
    "emergency_airway": "emergency",
    "medical_emergency_other": "emergency",
    "urgent_fracture": "urgent",
    "urgent_bleeding": "urgent",
    "dental_trauma_avulsion": "urgent",
    "urgent_swelling": "urgent",
    "out_of_scope": "info",
    "none": "none",
}

#: Labels that stop the dental information flow entirely.
HALTING: frozenset[Label] = frozenset(
    {"crisis_self_harm", "emergency_airway", "medical_emergency_other"}
)


def most_urgent(*labels: Label) -> Label:
    """Pick the highest-precedence label."""
    return min(labels, key=PRECEDENCE.index)
