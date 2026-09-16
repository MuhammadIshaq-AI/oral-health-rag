import { EMBED_MODEL, PASSAGES } from "@/lib/rag/knowledge";

export async function GET() {
  const configured = Boolean(process.env.GEMINI_API_KEY);
  return Response.json({
    ok: configured,
    chunks: PASSAGES.length,
    embedModel: EMBED_MODEL,
    ...(configured ? {} : { reason: "GEMINI_API_KEY is not set" }),
  });
}
