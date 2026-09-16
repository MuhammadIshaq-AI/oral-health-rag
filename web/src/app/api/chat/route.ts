import type { NextRequest } from "next/server";
import { GeminiError, chat, embedQuery, type ChatMessage } from "@/lib/rag/gemini";
import { EMBED_DIMS, EMBED_MODEL } from "@/lib/rag/knowledge";
import { SYSTEM_PROMPT, formatContext, isRefusal, parseCitations } from "@/lib/rag/prompt";
import { retrieve } from "@/lib/rag/retrieve";
import type { ChatResponse, Turn } from "@/lib/types";

// One embedding call + one chat call; 60s leaves plenty of headroom.
export const maxDuration = 60;

const MAX_MESSAGE = 1000;
const MAX_TURNS = 12;
const HISTORY_TURNS = 6; // last 3 question/answer pairs go to the model

function isTurn(t: unknown): t is Turn {
  const turn = t as Turn;
  return (
    !!turn &&
    (turn.role === "user" || turn.role === "assistant") &&
    typeof turn.content === "string"
  );
}

export async function POST(req: NextRequest) {
  const started = performance.now();

  let body: { message?: unknown; history?: unknown };
  try {
    body = await req.json();
  } catch {
    return Response.json({ detail: "Invalid JSON body." }, { status: 400 });
  }

  const message = typeof body.message === "string" ? body.message.trim() : "";
  if (!message || message.length > MAX_MESSAGE) {
    return Response.json(
      { detail: `Message must be 1–${MAX_MESSAGE} characters.` },
      { status: 400 },
    );
  }
  const history = Array.isArray(body.history)
    ? body.history
        .filter(isTurn)
        .slice(-MAX_TURNS)
        .map(({ role, content }) => ({ role, content: content.slice(0, 4000) }))
    : [];

  // Follow-ups like "how is it treated?" need the earlier question to find the right passages.
  // Combining them avoids spending an extra model call on rewriting the question.
  const previousQuestion = [...history].reverse().find((t) => t.role === "user")?.content;
  const searchText = previousQuestion ? `${previousQuestion}\n${message}` : message;

  try {
    const passages = retrieve(await embedQuery(searchText, EMBED_MODEL, EMBED_DIMS)).map((p, i) => ({
      ...p,
      n: i + 1,
    }));

    const messages: ChatMessage[] = [
      { role: "system", content: SYSTEM_PROMPT },
      ...history.slice(-HISTORY_TURNS),
      { role: "user", content: `Sources:\n\n${formatContext(passages)}\n\nQuestion: ${message}` },
    ];
    const answer = await chat(messages);
    const cited = new Set(parseCitations(answer, passages.length));

    const response: ChatResponse = {
      answer,
      refused: isRefusal(answer),
      latency_s: Math.round((performance.now() - started) / 10) / 100,
      sources: passages.map(({ n, id, title, section, url, publisher, license, score }) => ({
        n,
        id,
        title,
        section,
        url,
        publisher,
        license,
        score: Math.round(score * 1e4) / 1e4,
        cited: cited.has(n),
      })),
    };
    return Response.json(response);
  } catch (err) {
    if (err instanceof GeminiError) {
      return Response.json({ detail: err.message }, { status: err.status });
    }
    const timedOut = err instanceof DOMException && err.name === "TimeoutError";
    console.error("chat route error", err);
    return Response.json(
      {
        detail: timedOut
          ? "The assistant took too long to respond. Please try again."
          : "Something went wrong while answering. Please try again.",
      },
      { status: timedOut ? 504 : 500 },
    );
  }
}
