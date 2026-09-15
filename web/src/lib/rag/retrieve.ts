import { PASSAGES, type Passage } from "./knowledge";
import { CLINIC_PUBLISHER } from "./prompt";

export type Retrieved = Passage & { score: number };

const TOP_K = 5;
// Practice passages are searched separately so the small clinic corpus isn't outranked by the much
// larger NHS/WHO corpus, but only kept when actually relevant (cosine similarity).
const CLINIC_K = 2;
const CLINIC_MIN_SCORE = Number(process.env.CLINIC_MIN_SCORE ?? "0.6");

function dot(a: Float32Array, b: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += a[i] * b[i];
  return sum;
}

/** Practice passages first (when relevant), then the top general-guidance passages. */
export function retrieve(query: Float32Array): Retrieved[] {
  const scored = PASSAGES.map((p) => ({ ...p, score: dot(query, p.embedding) })).sort((a, b) => b.score - a.score);
  const clinic = scored
    .filter((p) => p.publisher === CLINIC_PUBLISHER && p.score >= CLINIC_MIN_SCORE)
    .slice(0, CLINIC_K);
  const chosen = new Set(clinic.map((p) => p.id));
  return [...clinic, ...scored.filter((p) => !chosen.has(p.id)).slice(0, TOP_K)];
}
