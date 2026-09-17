from app.rag.prompt import DISCLAIMER, NO_GUIDANCE
from app.rag.validate import is_refusal, parse_citations, split_sentences, validate_answer


def test_parse_citations_dedup_and_range() -> None:
    assert parse_citations("A [2]. B [1][2]. C [9].", 3) == [2, 1]


def test_valid_answer_passes() -> None:
    text = (
        f"Bleeding gums can be a sign of gum disease [1]. Brush twice a day [1][2].\n\n{DISCLAIMER}"
    )
    r = validate_answer(text, 2)
    assert not r.hard_fail
    assert r.citations == [1, 2]
    assert "disclaimer_appended" not in r.flags


def test_disclaimer_appended_and_invalid_marker_removed() -> None:
    r = validate_answer("Floss every day to clean between teeth [1][7].", 2)
    assert r.text.endswith(DISCLAIMER)
    assert "[7]" not in r.text
    assert {"disclaimer_appended", "invalid_citation_removed"} <= set(r.flags)


def test_uncited_answer_fails() -> None:
    r = validate_answer("You should brush your teeth twice every day. Floss once a day too.", 3)
    assert "no_citations" in r.flags and r.hard_fail


def test_low_coverage_fails() -> None:
    text = (
        "Brush twice daily with fluoride toothpaste [1]. Replace your brush every three months. "
        "Visit the dentist regularly for check-ups. Limit sugary drinks between meals."
    )
    assert "low_citation_coverage" in validate_answer(text, 1).flags


def test_diagnosis_blocked() -> None:
    r = validate_answer("It sounds like you have gum disease [1].", 1)
    assert "diagnosis" in r.flags and r.hard_fail
    assert "diagnosis" in validate_answer("You probably have an abscess [1].", 1).flags


def test_general_condition_statement_allowed() -> None:
    assert (
        "diagnosis"
        not in validate_answer("Bleeding gums can be a sign of gum disease [1].", 1).flags
    )


def test_prescription_blocked() -> None:
    for text in (
        "Take amoxicillin for the infection [1].",
        "Take 500 mg of paracetamol [1].",
        "Take two tablets twice a day [1].",
    ):
        assert "prescription" in validate_answer(text, 1).flags, text


def test_refusal_detected() -> None:
    r = validate_answer(NO_GUIDANCE, 3)
    assert r.is_refusal and not r.hard_fail
    assert is_refusal(r.text)


def test_exempt_sentences_do_not_need_citations() -> None:
    text = f"Rinse with warm salty water [1]. Please see a dentist if it gets worse. {DISCLAIMER}"
    assert "some_uncited_sentences" not in validate_answer(text, 1).flags


def test_split_sentences_handles_bullets() -> None:
    assert len(split_sentences("Steps:\n- Hold the crown [1].\n- Store in milk [1].")) == 3


def test_prompt_version_fallback() -> None:
    """A version may override only some prompts; the rest fall back to v1."""
    from app.rag.prompt import load_prompt

    assert load_prompt("system", "v2") != load_prompt("system", "v1")  # v2 exists
    assert load_prompt("triage", "v2") == load_prompt("triage", "v1")  # falls back
    assert load_prompt("rewrite", "v1s") == load_prompt("rewrite", "v1")
    assert "NO_ANSWER" in load_prompt("system", "v1s")
