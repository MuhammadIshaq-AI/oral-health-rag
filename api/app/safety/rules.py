"""Deterministic red-flag rules.

Each rule is a set of regular expressions over normalised text. A match is
ignored when a negation cue ("no", "not", "without", "isn't" …) appears in the
few words before it. Rules are deliberately conservative: a false alarm shows a
banner, a miss could delay emergency care. Every decision returns the exact
trigger phrases so it can be logged and audited.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.safety.labels import Label, most_urgent

_NEGATION = re.compile(
    r"\b(no|not|never|without|isn'?t|aren'?t|wasn'?t|haven'?t|hasn'?t|don'?t|doesn'?t|didn'?t|"
    r"denies|nor|zero|free of|stopped)\b"
)
_NEG_WINDOW_WORDS = 4

_SPELLING = {
    r"\bswolen\b": "swollen",
    r"\bswolled\b": "swollen",
    r"\bswelled\b": "swollen",
    r"\b(can't|cant|cannot|to|not|hardly) breath\b": r"\1 breathe",
    r"\bbreathin\b": "breathing",
    r"\bswallo\b": "swallow",
    r"\bcant\b": "can't",
    r"\bcannot\b": "can't",
    r"\bcan not\b": "can't",
    r"\bwont\b": "won't",
    r"\bdont\b": "don't",
    r"\bdoesnt\b": "doesn't",
    r"\bim\b": "i'm",
    r"\bteath\b": "teeth",
    r"\btooths\b": "teeth",
    r"\bbleading\b": "bleeding",
    r"\bjaw bone\b": "jawbone",
    r"\bknock out\b": "knocked out",
    r"\bnocked\b": "knocked",
    r"\bsuicidle\b": "suicidal",
}


def normalise(text: str) -> str:
    """Lowercase, unify apostrophes/whitespace, fix frequent misspellings and STT artefacts."""
    t = text.lower().replace("’", "'").replace("‘", "'").replace("`", "'")
    t = re.sub(r"[^\w\s'?.,!-]", " ", t)
    for pattern, repl in _SPELLING.items():
        t = re.sub(pattern, repl, t)
    return re.sub(r"\s+", " ", t).strip()


def _p(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts))


# ---- concept patterns -------------------------------------------------------
SWELLING = _p(
    r"\bswell\w*",
    r"\bswollen\b",
    r"\bpuff(y|ed|ing)? up\b",
    r"\bpuffy\b",
    r"\bblown up\b",
    r"\bbig lump\b",
    r"\blump\b",
)
FACE_NECK = _p(
    r"\bface\b",
    r"\bfacial\b",
    r"\bcheeks?\b",
    r"\bjaw\w*",
    r"\bneck\b",
    r"\beyes?\b",
    r"\bchin\b",
    r"\bunder (my |his |her |their |the )?tongue\b",
    r"\bfloor of (my |the )?mouth\b",
    r"\bthroat\b",
    r"\bside of (my |his |her |their )?(face|head)\b",
)
GUM_LIP = _p(r"\bgums?\b", r"\blips?\b", r"\btongue\b", r"\bmouth\b", r"\broof of\b")
SEVERE_MOD = _p(
    r"\bfever\w*",
    r"\btemperature\b",
    r"\bchills\b",
    r"\bshiver\w*",
    r"\bspread\w*",
    r"\bgetting (bigger|worse)\b",
    r"\bpus\b",
    r"\babscess\w*",
    r"\bhot and red\b",
    r"\bvery (big|large|bad)\b",
    r"\bhuge\b",
    r"\bclosing\b",
    r"\bgolf ball\b",
)
BREATH_DIFF = _p(
    r"\b(can't|hard to|trouble|difficult\w*|struggl\w*( to)?|unable to|hurts to|problems?|difficulty) (breathe|breathing)\b",
    r"\bshort(ness)? of breath\b",
    r"\bbreathing (is |getting )?(hard|difficult|noisy|funny|weird|strange)\b",
    r"\bchoking\b",
    r"\bthroat (is |feels )?(closing|tight)\b",
    r"\bgasping\b",
    r"\bwheez\w*",
    r"\bcan't get (any )?air\b",
    r"\bnot breathing properly\b",
)
SWALLOW_DIFF = _p(
    r"\b(can't|hard to|trouble|difficult\w*|struggl\w*( to)?|unable to|hurts to|painful to|problems?|difficulty) (swallow\w*)\b",
    r"\bdrool\w*",
    r"\bcan't (even )?swallow\b",
)
DENTAL_CONTEXT = _p(
    r"\bteeth\b",
    r"\btooth\b",
    r"\bdental\b",
    r"\bdentist\b",
    r"\bgums?\b",
    r"\bwisdom\b",
    r"\babscess\w*",
    r"\bextract\w*",
    r"\bjaw\w*",
    r"\bmouth\b",
    r"\btongue\b",
    r"\binfect\w*",
)
AVULSION = _p(
    r"\b(tooth|teeth|incisors?|molars?)( has| have| was| were| just| got| is)? (been )?(knocked|punched|kicked|smashed|bashed|pulled) (out|clean out|loose|out of place)\b",
    r"\bknocked (out )?(a |his |her |my |their |our |the |two |one |both )?(front |adult |permanent |top |bottom |baby )?(tooth|teeth)( out| loose)?\b",
    r"\b(tooth|teeth) (is |was )?(avulsed)\b",
    r"\bavulsion\b",
    r"\b(tooth|teeth) (came|come|fell|popped|flew) (right |clean )?out\b.{0,60}\b(hit|punch\w*|fell|fall|fight|kick\w*|accident|crash\w*|sport|footy|football|rugby|cricket|hockey|netball|basketball|bike|tackle\w*|elbow\w*|smash\w*|trampoline|skateboard\w*|scooter)\b",
    r"\b(hit|punch\w*|fell|fall|fight|kick\w*|accident|crash\w*|footy|football|rugby|cricket|hockey|netball|basketball|bike|tackle\w*|elbow\w*|smash\w*|trampoline|skateboard\w*|scooter)\b.{0,80}\b(tooth|teeth) (came|come|fell|popped|flew|got knocked|was knocked|is knocked) (right |clean )?out\b",
    r"\b(lost|lose) (a |his |her |my |their |the )?(front |adult |permanent )?(tooth|teeth) (playing|in a|in the|at|during|after a|after the|from a)\b",
    r"\b(tooth|teeth) (is |was |were |got |has been |have been |had been )?(pushed|knocked|shoved) (back|in|up|out of place|sideways|crooked)\b",
)
BLEED_STRONG = _p(
    r"\b(bleed\w*|blood)\b.{0,50}\b(won't|will not|doesn't|does not|isn't going to|not) (stop\w*|slow\w*|ease\w*)\b",
    r"\b(can't|unable to) stop (the |it |this )?(bleed\w*|blood)\b",
    r"\bsoak(ed|ing|s)? (through|thru)\b",
    r"\bpouring (out )?blood\b",
    r"\bblood (is )?pouring\b",
    r"\bgush\w*\b",
    r"\b(lots|heaps|so much|a lot) of blood\b",
    r"\bheavy bleeding\b",
    r"\bbleeding (heavily|badly|a lot|non ?stop)\b",
    r"\bmouth (is )?full of blood\b",
    r"\bblood clots? (keep|keeps) (coming|forming)\b",
)
BLEED_WEAK = _p(
    r"\bstill bleeding\b",
    r"\bkeeps? (on )?bleeding\b",
    r"\bbleeding for (hours|\d+ ?hours?|over an? hour|ages|a long time)\b",
)
BLEED_PROCEDURE = _p(
    r"\bextract\w*",
    r"\bpulled\b",
    r"\bremov\w*",
    r"\btaken out\b",
    r"\bsurgery\b",
    r"\bsocket\b",
    r"\bout (today|yesterday|this morning)\b",
    r"\bhours?\b",
    r"\bblood thinner\w*",
    r"\bwarfarin\b",
)
FRACTURE = _p(
    r"\b(broken|broke|break|fractur\w*|dislocat\w*|cracked|smashed) (my |his |her |their |the |a |your )?(jaw|jawbone|cheekbone|cheek bone|mandible|lower jaw|upper jaw)\b",
    r"\b(jaw|jawbone|mandible) (is |looks |feels |might be |may be |could be |seems )?(broken|fractured|out of place|crooked|misaligned|dislocated|shifted|off to one side)\b",
)
BITE_CHANGE = _p(
    r"\b(can't) (close|shut) (my |his |her |their |the )?(mouth|jaw)\b",
    r"\bteeth (don't|do not|won't|no longer) (meet|fit|line up|come together|bite)\b",
    r"\bbite (feels |is )?(wrong|off|different|crooked)\b",
    r"\bjaw (is )?stuck\b",
)
INJURY = _p(
    r"\bhit\b",
    r"\bpunch\w*",
    r"\bfell\b",
    r"\bfall\w*",
    r"\baccident\b",
    r"\bcrash\w*",
    r"\bkick\w*",
    r"\belbow\w*",
    r"\btackle\w*",
    r"\bsmash\w*",
    r"\bfight\b",
    r"\bassault\w*",
    r"\bbashed\b",
    r"\bstruck\b",
    r"\bslammed\b",
    r"\binjur\w*",
)
SELF_HARM = _p(
    r"\b(kill\w*|hurt\w*|harm\w*|cut\w*) (my ?self|myself)\b",
    r"\bsuicid\w*",
    r"\b(end|ending|ended) (it all|my life|things)\b",
    r"\bwant(ed)? to die\b",
    r"\bwanna die\b",
    r"\b(don't|do not) want to (live|be alive|be here|wake up)\b",
    r"\bbetter off dead\b",
    r"\bno (reason|point) (to|in) (keep |go on )?(live|living|going on)\b",
    r"\btake my (own )?life\b",
    r"\bself[- ]harm\w*",
)
MEDICAL_EMERGENCY = _p(
    r"\bchest (pain|pains|tightness|is tight|feels tight|pressure)\b",
    r"\bheart attack\b",
    r"\bstroke\b",
    r"\bface (is )?droop\w*",
    r"\bslurr\w*",
    r"\bcan't (move|feel) (my |his |her |their )?(arm|leg|side)\b",
    r"\banaphyla\w*",
    r"\bepi ?pen\b",
    r"\bunconscious\b",
    r"\bpassed out\b",
    r"\bcollaps\w*",
    r"\bnot breathing\b",
    r"\bseizure\w*",
    r"\bhaving a fit\b",
    r"\boverdos\w*",
    r"\btook too many (pills|tablets)\b",
    r"\b(lips|tongue|throat) (is |are )?swelling.{0,40}\b(allerg\w*|hives|bee|sting|peanut|nut)\b",
    r"\ballergic reaction\b",
    r"\bunresponsive\b",
    r"\bbleeding (from|out of) (my |his |her )?(ear|nose) after\b",
)
OUT_OF_SCOPE = _p(
    r"\b(weather|footy score|stock price|share price|bitcoin|crypto|recipe|tax return|centrelink payment|visa application|"
    r"lottery|horoscope|python code|javascript|write (me )?a poem|capital of|who won)\b",
)
PREVENTION = re.compile(r"\b(prevent\w*|mouthguards?|avoid\w*|protect\w*|reduce the risk)\b")
GENERAL_QUESTION = re.compile(
    r"^(what|why|how|can|could|does|do|is|are|when|should)\b.{0,60}\b(cause|causes|caused|mean|means|happen|common|normal|treat\w*|prevent\w*|sign|signs|types?|reasons?)\b"
)
PERSONAL = _p(
    r"\b(my|i|i'm|i've|me|mine|we|our|us)\b",
    r"\b(his|her|their|he|she|they)\b",
    r"\b(son|daughter|child|kid|baby|toddler|mum|mom|dad|husband|wife|partner|friend|mother|father|grandma|grandpa|nan|pop)\b",
)


@dataclass
class RuleDecision:
    """Result of the deterministic rules."""

    label: Label
    triggers: list[str] = field(default_factory=list)
    candidates: dict[str, list[str]] = field(default_factory=dict)


def _hits(pattern: re.Pattern[str], text: str, negatable: bool = True) -> list[str]:
    found = []
    for m in pattern.finditer(text):
        if negatable:
            before = text[: m.start()].split()[-_NEG_WINDOW_WORDS:]
            if before and _NEGATION.search(" ".join(before)):
                continue
        found.append(m.group(0).strip())
    return found


def classify_rules(text: str) -> RuleDecision:
    """Apply all rules; return the most urgent label and its trigger phrases."""
    t = normalise(text)
    cand: dict[str, list[str]] = {}

    if sh := _hits(SELF_HARM, t, negatable=False):  # never negated: err on the side of support
        cand["crisis_self_harm"] = sh

    swelling = _hits(SWELLING, t)
    face = _hits(FACE_NECK, t)
    breath = _hits(BREATH_DIFF, t)
    swallow = _hits(SWALLOW_DIFF, t)
    dental = _hits(DENTAL_CONTEXT, t, negatable=False)

    if medical := _hits(MEDICAL_EMERGENCY, t):
        cand["medical_emergency_other"] = medical
    if breath and (swelling or dental):
        cand["emergency_airway"] = breath + swelling
    elif breath:
        cand["medical_emergency_other"] = cand.get("medical_emergency_other", []) + breath
    if swallow and (swelling or _hits(SEVERE_MOD, t) or dental):
        cand["emergency_airway"] = cand.get("emergency_airway", []) + swallow + swelling

    fracture = _hits(FRACTURE, t)
    bite = _hits(BITE_CHANGE, t)
    injury = _hits(INJURY, t, negatable=False)
    if fracture or (bite and injury):
        cand["urgent_fracture"] = fracture + (bite + injury if bite and injury else [])

    strong = _hits(BLEED_STRONG, t)
    weak = _hits(BLEED_WEAK, t)
    if strong or (weak and _hits(BLEED_PROCEDURE, t, negatable=False)):
        cand["urgent_bleeding"] = strong + weak

    if av := _hits(AVULSION, t):
        prevention_only = bool(PREVENTION.search(t)) and not _hits(PERSONAL, t, negatable=False)
        if not prevention_only:
            cand["dental_trauma_avulsion"] = av

    if swelling:
        severe = _hits(SEVERE_MOD, t)
        gum = _hits(GUM_LIP, t, negatable=False)
        is_general = bool(GENERAL_QUESTION.search(t)) and not _hits(PERSONAL, t, negatable=False)
        if not is_general and (face or (gum and severe)):
            cand["urgent_swelling"] = swelling + face + severe

    if not cand and (oos := _hits(OUT_OF_SCOPE, t, negatable=False)) and not dental:
        cand["out_of_scope"] = oos

    if not cand:
        return RuleDecision("none")
    label = most_urgent(*cand.keys())  # type: ignore[arg-type]
    triggers = list(dict.fromkeys(cand[label]))
    return RuleDecision(label, triggers, {k: list(dict.fromkeys(v)) for k, v in cand.items()})
