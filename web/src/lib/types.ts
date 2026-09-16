export type Source = {
  n: number;
  /** Passage id in knowledge.json (lets the eval look up the exact text the model saw). */
  id: string;
  title: string;
  section: string;
  url: string;
  publisher: string;
  license: string;
  score: number;
  cited: boolean;
};

export type ChatResponse = {
  answer: string;
  refused: boolean;
  sources: Source[];
  latency_s: number;
};

export type Turn = { role: "user" | "assistant"; content: string };

export type Message = Turn & {
  id: string;
  sources?: Source[];
  refused?: boolean;
  error?: boolean;
  latency?: number;
  /** On failed answers: the question to resend and the id of the user message that asked it. */
  retry?: { question: string; userId: string };
};
