import data from "@/data/knowledge.json";

/** A knowledge-base passage with its L2-normalised embedding (see scripts/export_web_index.py). */
export type Passage = {
  id: string;
  text: string;
  title: string;
  section: string;
  url: string;
  publisher: string;
  license: string;
  embedding: Float32Array;
};

type RawPassage = Omit<Passage, "embedding"> & { embedding: string };

function decode(base64: string): Float32Array {
  const bytes = Buffer.from(base64, "base64");
  // Copy into a fresh buffer: a Buffer's byteOffset isn't guaranteed to be a multiple of 4.
  return new Float32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
}

export const EMBED_MODEL: string = data.model;
export const EMBED_DIMS: number = data.dims;

// Decoded once per function instance, then reused across requests.
export const PASSAGES: Passage[] = (data.chunks as RawPassage[]).map((p) => ({
  ...p,
  embedding: decode(p.embedding),
}));
