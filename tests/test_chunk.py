import itertools

from ingest.chunk import chunk_markdown, whitespace_token_counter
from ingest.clean import clean_title, strip_boilerplate


def _para(word: str, n_words: int) -> str:
    return " ".join([word] * (n_words - 1)) + "."


def test_heading_path_and_budget() -> None:
    md = "# Gum disease\n\n" + "\n\n".join(
        f"## Section {i}\n\n{_para('gums', 120)}\n\n### Sub {i}\n\n{_para('teeth', 120)}"
        for i in range(4)
    )
    chunks = chunk_markdown(md, "Gum disease", whitespace_token_counter, 300, 500, 0.15)
    assert len(chunks) >= 3
    assert all(c.tokens <= 500 for c in chunks)
    assert chunks[0].section.startswith("Section 0")
    # The page-title H1 is not repeated as a section.
    assert all("Gum disease" not in s for c in chunks for s in c.sections)


def test_overlap_carries_trailing_content() -> None:
    paras = [f"Paragraph {i} " + _para(f"w{i}", 60) for i in range(20)]
    chunks = chunk_markdown("\n\n".join(paras), "T", whitespace_token_counter, 300, 500, 0.15)
    assert len(chunks) >= 2
    for prev, nxt in itertools.pairwise(chunks):
        overlap_words = prev.text.split()[-40:]
        assert " ".join(overlap_words) in nxt.text  # ~15% of a ~480-token chunk is carried over
        assert nxt.text.split("\n\n")[0] in prev.text


def test_small_sections_merge() -> None:
    md = "\n\n".join(f"## S{i}\n\nShort text about teeth number {i}." for i in range(10))
    chunks = chunk_markdown(md, "Page", whitespace_token_counter, 300, 500, 0.15)
    assert len(chunks) == 1
    assert chunks[0].section == "S0"


def test_long_block_split_into_sentences() -> None:
    long_para = " ".join(
        f"Sentence number {i} is about brushing your teeth well." for i in range(120)
    )
    chunks = chunk_markdown(long_para, "Page", whitespace_token_counter, 300, 500, 0.15)
    assert len(chunks) >= 2
    assert all(c.tokens <= 500 for c in chunks)


def test_empty() -> None:
    assert chunk_markdown("", "x") == []


def test_clean_helpers() -> None:
    assert clean_title("Bleeding gums | healthdirect") == "Bleeding gums"
    assert strip_boilerplate("Hello\nShare\nWas this page helpful? Yes\nBye") == "Hello\nBye"
