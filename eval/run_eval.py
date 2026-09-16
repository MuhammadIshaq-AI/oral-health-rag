"""Mini evaluation: answer each patient question, then score groundedness with an LLM judge.

Metrics
- in-scope:  grounded / partially grounded / ungrounded / false refusal, citation rate, retrieval hit@k
- out-of-scope: correct refusal rate (the bot should decline rather than use outside knowledge)

Results are written incrementally, so a run interrupted by rate limits can be resumed.
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

from rag.chain import Answer, OralHealthRAG, format_context  # noqa: E402
from rag.llm import get_llm  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

JUDGE_PROMPT = """You are a strict fact-checking judge for a medical RAG chatbot.
Given numbered SOURCES and an ANSWER, decide whether every factual claim in the ANSWER is supported
by the SOURCES. Ignore generic advice to see a dentist/doctor. Do not use your own medical knowledge.

Verdicts:
- "refusal": the answer declines / says the information isn't available, making no substantive claims.
- "grounded": every factual claim is supported by the sources.
- "partially_grounded": most claims are supported but at least one is not.
- "ungrounded": the main claims are not supported by the sources.

Respond with JSON only:
{"verdict": "...", "unsupported_claims": ["..."], "reason": "one sentence"}"""


def judge(llm, contexts: list[dict], answer: str) -> dict:
    msg = llm.invoke(
        [
            SystemMessage(JUDGE_PROMPT),
            HumanMessage(f"SOURCES:\n\n{format_context(contexts)}\n\nANSWER:\n{answer}"),
        ]
    )
    match = re.search(r"\{.*\}", msg.content, re.S)
    try:
        out = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        out = {}
    if out.get("verdict") not in {"refusal", "grounded", "partially_grounded", "ungrounded"}:
        out = {"verdict": "judge_error", "unsupported_claims": [], "reason": msg.content[:200]}
    return out


def load_passages() -> dict[str, dict]:
    """Passage texts shipped with the web app, keyed by id."""
    path = HERE.parent / "web" / "src" / "data" / "knowledge.json"
    return {c["id"]: c for c in json.loads(path.read_text(encoding="utf-8"))["chunks"]}


def ask_api(api_url: str, question: str, passages: dict[str, dict]) -> Answer:
    """Ask the deployed Next.js app, so the eval measures production retrieval and prompting."""
    resp = requests.post(f"{api_url.rstrip('/')}/api/chat", json={"message": question, "history": []}, timeout=180)
    data = resp.json()
    if not resp.ok:
        raise RuntimeError(f"API error {resp.status_code}: {data.get('detail')}")
    contexts = [{**s, "text": passages.get(s["id"], {}).get("text", "")} for s in data["sources"]]
    return Answer(
        question=question,
        answer=data["answer"],
        contexts=contexts,
        cited=[s["n"] for s in data["sources"] if s["cited"]],
        latency_s=data["latency_s"],
    )


def summarise(rows: list[dict], model: str, judge_model: str) -> str:
    ins = [r for r in rows if r["category"] == "in_scope"]
    oos = [r for r in rows if r["category"] == "out_of_scope"]
    v_in = Counter(r["verdict"] for r in ins)
    pct = lambda n, d: f"{100 * n / d:.0f}%" if d else "n/a"  # noqa: E731

    correct_refusals = sum(r["verdict"] == "refusal" or r["bot_refused"] for r in oos)
    answered = [r for r in ins if r["verdict"] != "refusal"]
    lines = [
        "# Evaluation summary",
        "",
        f"- Chat model: `{model}`  ·  Judge model: `{judge_model}`",
        f"- Questions: {len(rows)} ({len(ins)} in-scope, {len(oos)} out-of-scope)",
        "",
        "## In-scope questions",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Grounded | {v_in['grounded']}/{len(ins)} ({pct(v_in['grounded'], len(ins))}) |",
        f"| Partially grounded | {v_in['partially_grounded']}/{len(ins)} ({pct(v_in['partially_grounded'], len(ins))}) |",
        f"| Ungrounded | {v_in['ungrounded']}/{len(ins)} ({pct(v_in['ungrounded'], len(ins))}) |",
        f"| Refused (false refusal) | {v_in['refusal']}/{len(ins)} ({pct(v_in['refusal'], len(ins))}) |",
        f"| Answers with ≥1 valid citation | {sum(bool(r['cited']) for r in answered)}/{len(answered)} ({pct(sum(bool(r['cited']) for r in answered), len(answered))}) |",
        f"| Retrieval hit@k (expected page retrieved) | {sum(r['retrieval_hit'] for r in ins)}/{len(ins)} ({pct(sum(r['retrieval_hit'] for r in ins), len(ins))}) |",
        "",
        "## Out-of-scope questions",
        "",
        f"Correctly declined: {correct_refusals}/{len(oos)} ({pct(correct_refusals, len(oos))})",
        "",
        "## Per-question results",
        "",
        "| id | category | verdict | cited | hit@k | question |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        hit = "—" if r["category"] == "out_of_scope" else ("✓" if r["retrieval_hit"] else "✗")
        lines.append(
            f"| {r['id']} | {r['category']} | {r['verdict']} | {r['cited'] or '—'} | {hit} | {r['question']} |"
        )
    flagged = [r for r in rows if r["verdict"] in {"partially_grounded", "ungrounded"}]
    if flagged:
        lines += ["", "## Unsupported claims flagged by the judge", ""]
        for r in flagged:
            claims = "; ".join(r["unsupported_claims"]) or r["reason"]
            lines.append(f"- **{r['id']}** ({r['verdict']}): {claims}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge-provider", default=None, help="defaults to LLM_PROVIDER")
    parser.add_argument("--judge-model", default=None, help="defaults to the chat model")
    # Gemini's free tier is rate-limited to roughly 10 requests/minute; 6s between calls stays under it.
    parser.add_argument("--sleep", type=float, default=6.0, help="seconds between API calls")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fresh", action="store_true", help="ignore previous partial results")
    parser.add_argument(
        "--api-url",
        default=None,
        help="evaluate a running web app (e.g. https://scope-dental-assistant.vercel.app) instead of the local Python pipeline",
    )
    args = parser.parse_args()

    questions = [json.loads(l) for l in (HERE / "questions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    questions = questions[: args.limit]

    rag = None if args.api_url else OralHealthRAG()
    passages = load_passages() if args.api_url else {}
    judge_llm = get_llm(args.judge_provider, args.judge_model, temperature=0.0)

    RESULTS.mkdir(exist_ok=True)
    partial = RESULTS / "results.partial.jsonl"
    done = {}
    if partial.exists() and not args.fresh:
        done = {r["id"]: r for r in map(json.loads, partial.read_text(encoding="utf-8").splitlines())}

    with partial.open("a" if done else "w", encoding="utf-8") as f:
        for q in questions:
            if q["id"] in done:
                continue
            try:
                ans = ask_api(args.api_url, q["question"], passages) if args.api_url else rag.ask(q["question"])
            except RuntimeError as exc:  # e.g. daily quota reached; progress so far is saved, rerun to resume
                print(f"stopping at {q['id']}: {exc}")
                break
            time.sleep(args.sleep)
            verdict = judge(judge_llm, ans.contexts, ans.answer)
            time.sleep(args.sleep)

            row = {
                **q,
                "answer": ans.answer,
                "bot_refused": ans.is_refusal,
                "cited": ans.cited,
                "retrieved": [c["url"] for c in ans.contexts],
                # expected_source may list acceptable pages separated by "|"
                "retrieval_hit": bool(q["expected_source"])
                and any(s in c["url"] for s in q["expected_source"].split("|") for c in ans.contexts),
                "latency_s": ans.latency_s,
                **verdict,
            }
            done[q["id"]] = row
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{q['id']} {row['verdict']:<20} cited={row['cited']} hit={row['retrieval_hit']}  {q['question'][:60]}")

    rows = [done[q["id"]] for q in questions if q["id"] in done]
    (RESULTS / "results.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    chat_model = f"deployed app ({args.api_url})" if args.api_url else rag.llm.model_name
    summary = summarise(rows, chat_model, judge_llm.model_name)
    (RESULTS / "summary.md").write_text(summary, encoding="utf-8")
    print("\n" + summary.split("## Per-question")[0])


if __name__ == "__main__":
    main()
