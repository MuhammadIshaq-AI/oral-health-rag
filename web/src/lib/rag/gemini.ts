const API = "https://generativelanguage.googleapis.com/v1beta";

export class GeminiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function apiKey(): string {
  const key = process.env.GEMINI_API_KEY;
  if (!key) {
    throw new GeminiError(
      "GEMINI_API_KEY is not set. Add it in your Vercel project settings (or web/.env.local for local development).",
      500,
    );
  }
  return key;
}

// Overload (503), rate-limit (429) and transient server errors are usually short-lived.
const RETRYABLE = new Set([429, 500, 502, 503, 504]);
const RETRY_DELAYS_MS = [1500, 4000];

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function post(url: string, body: unknown, headers: Record<string, string>, timeoutMs: number) {
  for (let attempt = 0; ; attempt++) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
      cache: "no-store",
    });
    if (res.ok) return res.json();

    const detail = await res.text().catch(() => "");
    if (RETRYABLE.has(res.status) && attempt < RETRY_DELAYS_MS.length) {
      await sleep(RETRY_DELAYS_MS[attempt]);
      continue;
    }

    // Log the provider's raw error for debugging; show patients a plain message.
    console.error(`Gemini HTTP ${res.status}: ${detail.slice(0, 500)}`);
    if (res.status === 429) {
      throw new GeminiError(
        "The assistant has reached its usage limit for now. Please try again later, or contact the practice on WhatsApp.",
        429,
      );
    }
    if (res.status >= 500) {
      throw new GeminiError("The AI model is very busy right now. Please try again in a moment.", 503);
    }
    throw new GeminiError("The assistant couldn't process that request. Please try again.", 502);
  }
}

/** Embeds a search query and L2-normalises it to match the exported passage vectors. */
export async function embedQuery(text: string, model: string, dims: number): Promise<Float32Array> {
  const data = await post(
    `${API}/models/${model}:embedContent`,
    {
      model: `models/${model}`,
      content: { parts: [{ text }] },
      taskType: "RETRIEVAL_QUERY",
      outputDimensionality: dims,
    },
    { "x-goog-api-key": apiKey() },
    20_000,
  );
  const vector = Float32Array.from(data.embedding.values as number[]);
  const norm = Math.hypot(...vector) || 1;
  for (let i = 0; i < vector.length; i++) vector[i] /= norm;
  return vector;
}

export type ChatMessage = { role: "system" | "user" | "assistant"; content: string };

/** Gemini chat completion via the OpenAI-compatible endpoint. */
export async function chat(messages: ChatMessage[]): Promise<string> {
  const data = await post(
    `${API}/openai/chat/completions`,
    {
      model: process.env.LLM_MODEL || "gemini-3.6-flash",
      messages,
      temperature: 0.1,
      max_completion_tokens: 1024,
      // Thinking tokens count against the output limit and add latency; grounded answering doesn't need them.
      reasoning_effort: "none",
    },
    { Authorization: `Bearer ${apiKey()}` },
    45_000,
  );
  return (data.choices?.[0]?.message?.content ?? "").trim();
}
