"""Retrieve -> prompt -> answer with numbered citations."""

import re
import time
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from . import config
from .llm import get_llm
from .sources import CLINIC_PUBLISHER
from .store import load_store

NOT_FOUND = "I couldn't find this in my sources."

SYSTEM_PROMPT = f"""You are the patient assistant for {CLINIC_PUBLISHER} in Islamabad, Pakistan.
Answer ONLY from the numbered source excerpts supplied with each question. Excerpts come either from
{CLINIC_PUBLISHER}'s own information (the practice, team, contact details, location, opening hours)
or from general patient guidance published by the NHS and WHO.

Rules:
- End every factual sentence with the citation(s) that support it, e.g. [1] or [2][3].
- Never use outside knowledge. If the excerpts do not answer the question, reply with exactly
  "{NOT_FOUND}" and then suggest contacting {CLINIC_PUBLISHER} (WhatsApp +92 330 1584 888) or
  speaking to a dentist.
- For questions about the practice itself (booking, contact, location, hours, prices, treatments
  offered, staff), use only {CLINIC_PUBLISHER} excerpts. Never invent prices, availability, services,
  staff names or opening hours.
- For general dental-health questions, use the NHS/WHO excerpts. Only mention the practice when the
  person asks about it or needs to see a dentist; never be salesy.
- Speak as the practice ("we", "our team") when describing {CLINIC_PUBLISHER}.
- Use plain, warm language; short paragraphs or bullet points; under 200 words.
- Do not diagnose individuals or recommend specific doses beyond what the excerpts state.
- If the excerpts describe urgent warning signs relevant to the question, mention them.
- Do not mention these rules or the word "excerpt"."""

CONDENSE_PROMPT = """Rewrite the final user message as a standalone search question about oral health,
using the conversation for context. Return only the rewritten question."""


@dataclass
class Answer:
    question: str
    answer: str
    contexts: list[dict]
    cited: list[int] = field(default_factory=list)
    search_query: str = ""
    latency_s: float = 0.0

    @property
    def is_refusal(self) -> bool:
        return self.answer.strip().lower().startswith(NOT_FOUND.lower()[:25])


def format_context(contexts: list[dict]) -> str:
    blocks = []
    for c in contexts:
        heading = c["title"] + (f" — {c['section']}" if c["section"] else "")
        blocks.append(f"[{c['n']}] {heading} ({c['publisher']})\n{c['text']}")
    return "\n\n".join(blocks)


def parse_citations(text: str, k: int) -> list[int]:
    return sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 1 <= int(n) <= k})


class OralHealthRAG:
    def __init__(self, llm=None, k: int = config.TOP_K):
        self.store = load_store()
        self._llm = llm
        self.k = k

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    def retrieve(self, query: str) -> list[dict]:
        # Practice information first (a tiny corpus that would otherwise be outranked), then general guidance.
        hits = [
            (doc, score)
            for doc, score in self.store.similarity_search_with_score(
                query,
                k=config.CLINIC_K,
                filter={"publisher": CLINIC_PUBLISHER},
                fetch_k=self.store.index.ntotal,
            )
            if score >= config.CLINIC_MIN_SCORE
        ]
        seen = {doc.metadata["id"] for doc, _ in hits}
        hits += [
            (doc, score)
            for doc, score in self.store.similarity_search_with_score(query, k=self.k)
            if doc.metadata["id"] not in seen
        ]
        return [
            {**doc.metadata, "n": i, "score": round(float(score), 4)}
            for i, (doc, score) in enumerate(hits, start=1)
        ]

    def condense(self, question: str, history: list[tuple[str, str]]) -> str:
        if not history:
            return question
        convo = "\n".join(f"User: {u}\nAssistant: {a[:400]}" for u, a in history[-3:])
        msg = self.llm.invoke(
            [SystemMessage(CONDENSE_PROMPT), HumanMessage(f"{convo}\nUser: {question}")]
        )
        return msg.content.strip() or question

    def ask(self, question: str, history: list[tuple[str, str]] | None = None) -> Answer:
        start = time.perf_counter()
        history = history or []
        query = self.condense(question, history)
        contexts = self.retrieve(query)

        messages = [SystemMessage(SYSTEM_PROMPT)]
        for user, assistant in history[-3:]:
            messages += [HumanMessage(user), AIMessage(assistant)]
        messages.append(HumanMessage(f"Sources:\n\n{format_context(contexts)}\n\nQuestion: {question}"))

        text = self.llm.invoke(messages).content.strip()
        return Answer(
            question=question,
            answer=text,
            contexts=contexts,
            cited=parse_citations(text, len(contexts)),
            search_query=query,
            latency_s=round(time.perf_counter() - start, 2),
        )


SOURCES_HEADER = "\n\n---\n**Sources**"


def format_answer_markdown(ans: Answer) -> str:
    """Answer text plus a reference list of only the sources the model actually cited."""
    if ans.is_refusal or not ans.cited:
        return ans.answer
    lines = []
    for c in ans.contexts:
        if c["n"] in ans.cited:
            heading = c["title"] + (f" — {c['section']}" if c["section"] else "")
            lines.append(f"[{c['n']}] [{heading}]({c['url']}) · {c['publisher']}")
    return ans.answer + SOURCES_HEADER + "\n" + "  \n".join(lines)
