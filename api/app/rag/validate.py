"""Output validation: citation coverage, diagnosis / prescription guards, disclaimer.

The system prompt asks the model to follow the grounding and safety rules; this
module *checks* that it did. Violations are returned as flags (logged for
research) and the pipeline either repairs the answer, regenerates once, or
falls back to the no-guidance message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.rag.prompt import DISCLAIMER, NO_GUIDANCE

CITATION = re.compile(r"\[(\d{1,2})\]")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[•*-])|\n+")

# Sentences that do not need a citation.
_EXEMPT = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^this is general information",
        r"^(i'm|i am) (sorry|not able)",
        r"^(please )?(talk to|see|contact|call|ask) (a|your) (dentist|doctor|pharmacist|health)",
        r"call healthdirect",
        r"^.{0,80}:$",  # list lead-ins ("Common causes include:")
        r"^(i hope|hope) this helps",
        r"^i don't have reliable australian guidance",
    )
]

DIAGNOSIS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\byou (probably |likely |most likely |definitely |may |might |could )?(have|has|are suffering from|'ve got|have got) "
        r"(a |an )?(gingivitis|periodontitis|gum disease|an? abscess|abscess|tooth decay|cavit|oral cancer|mouth cancer|"
        r"thrush|infection|pericoronitis|dry socket|oral lichen|leukoplakia|tmj|bruxism)",
        r"\b(it|this) (sounds|looks) like you (have|'ve got)",
        r"\bi (think|believe|suspect) (you|it) (have|has|is)",
        r"\byour diagnosis\b",
    )
]

PRESCRIPTION = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b\d+(\.\d+)?\s?(mg|mcg|µg|ml|milligrams?)\b",
        r"\b(amoxicillin|penicillin|metronidazole|clindamycin|augmentin|cephalexin|doxycycline|"
        r"erythromycin|tramadol|codeine|oxycodone|endone|panadeine forte|pilocarpine|chlorhexidine 0\.2)",
        r"\b(take|use) .{0,20}(antibiotics?|prescription)\b",
        r"\b(\d+|one|two|three) (tablets?|capsules?|pills?) (every|a day|daily|twice)",
    )
]


@dataclass
class ValidationResult:
    """Outcome of validating one answer."""

    text: str
    flags: list[str] = field(default_factory=list)
    citations: list[int] = field(default_factory=list)
    uncited_sentences: list[str] = field(default_factory=list)
    is_refusal: bool = False

    @property
    def hard_fail(self) -> bool:
        """Violations that require regeneration rather than repair."""
        return any(
            f in self.flags
            for f in ("diagnosis", "prescription", "no_citations", "low_citation_coverage")
        )


def split_sentences(text: str) -> list[str]:
    """Split answer text into sentence-like units (bullets count as sentences)."""
    parts = [p.strip(" \t•*-") for p in _SENT_SPLIT.split(text)]
    return [p for p in parts if p and len(p) > 2]


def parse_citations(text: str, n_passages: int) -> list[int]:
    """Valid, de-duplicated citation numbers in order of first appearance."""
    seen: list[int] = []
    for m in CITATION.finditer(text):
        n = int(m.group(1))
        if 1 <= n <= n_passages and n not in seen:
            seen.append(n)
    return seen


#: Small models copy a long refusal sentence out of the prompt verbatim, so the
#: short-prompt variants ask for this sentinel instead; both mean "no answer".
NO_ANSWER_TOKEN = "NO_ANSWER"


def is_refusal(text: str) -> bool:
    """True if the answer is the no-guidance message or the NO_ANSWER sentinel."""
    stripped = text.strip()
    return stripped.upper().startswith(NO_ANSWER_TOKEN) or stripped.lower().startswith(
        NO_GUIDANCE[:40].lower()
    )


def _needs_citation(sentence: str) -> bool:
    body = CITATION.sub("", sentence).strip()
    if len(body.split()) < 4:
        return False
    return not any(p.search(body) for p in _EXEMPT)


def validate_answer(text: str, n_passages: int, min_coverage: float = 0.8) -> ValidationResult:
    """Check and lightly repair an answer. Repairs: invalid markers removed, disclaimer appended."""
    flags: list[str] = []
    text = text.strip()

    if is_refusal(text):
        return ValidationResult(
            text=f"{NO_GUIDANCE}\n\n{DISCLAIMER}", flags=["refusal"], is_refusal=True
        )

    def _drop_invalid(m: re.Match[str]) -> str:
        return m.group(0) if 1 <= int(m.group(1)) <= n_passages else ""

    repaired = CITATION.sub(_drop_invalid, text)
    if repaired != text:
        flags.append("invalid_citation_removed")
        text = repaired

    body = text.replace(DISCLAIMER, "").strip()
    if any(p.search(body) for p in DIAGNOSIS):
        flags.append("diagnosis")
    if any(p.search(body) for p in PRESCRIPTION):
        flags.append("prescription")

    sentences = [s for s in split_sentences(body) if _needs_citation(s)]
    uncited = [s for s in sentences if not CITATION.search(s)]
    citations = parse_citations(body, n_passages)
    if not citations:
        flags.append("no_citations")
    elif sentences and (1 - len(uncited) / len(sentences)) < min_coverage:
        flags.append("low_citation_coverage")
    elif uncited:
        flags.append("some_uncited_sentences")

    if DISCLAIMER.lower() not in text.lower():
        flags.append("disclaimer_appended")
        text = f"{text}\n\n{DISCLAIMER}"
    return ValidationResult(text=text, flags=flags, citations=citations, uncited_sentences=uncited)


CORRECTIVE_NOTE = (
    "Your previous answer broke the rules: {problems}. Rewrite it, keeping the same facts. "
    "Use only the passages, do not diagnose, do not mention prescription medicines or doses, "
    "and end with the disclaimer line.{uncited}"
)
UNCITED_NOTE = (
    "\nThese sentences had no citation — add the passage number(s) they came from, like [1], "
    "at the end of each:\n{sentences}"
    "\nIf that is hard, drop the bullet list and write 3 to 5 plain sentences instead, each one "
    "ending with its passage number before the full stop."
)


def corrective_note(result: ValidationResult) -> str:
    """Retry instruction naming the exact problems (and sentences) to fix."""
    uncited = ""
    if result.uncited_sentences:
        listed = "\n".join(f"- {s}" for s in result.uncited_sentences[:8])
        uncited = UNCITED_NOTE.format(sentences=listed)
    return CORRECTIVE_NOTE.format(problems=", ".join(result.flags), uncited=uncited)
