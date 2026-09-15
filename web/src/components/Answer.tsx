"use client";

import { useState, type ReactNode } from "react";
import { Check, ChevronDown, Copy, ExternalLink, SearchX } from "lucide-react";
import type { Message, Source } from "@/lib/types";

export function AnswerCard({ message: m }: { message: Message }) {
  const sources = m.sources ?? [];
  const cited = sources.filter((s) => s.cited);
  const plain =
    m.content +
    (cited.length
      ? "\n\nSources:\n" + cited.map((s) => `[${s.n}] ${s.title} — ${s.url}`).join("\n")
      : "");

  return (
    <article className="rounded-3xl rounded-tl-lg border border-border bg-surface px-5 py-4 shadow-card sm:px-6 sm:py-5">
      <AnswerText text={m.content} sources={sources} />
      <SourceList sources={sources} />
      <div className="mt-4 flex items-center justify-between gap-3 border-t border-border pt-3 text-xs text-muted">
        <span className="tabular-nums">
          {cited.length ? `${cited.length} source${cited.length > 1 ? "s" : ""} cited` : "No citations"}
          {m.latency !== undefined && ` · ${m.latency.toFixed(1)}s`}
        </span>
        <CopyButton text={plain} />
      </div>
    </article>
  );
}

export function RefusalCard({ message: m }: { message: Message }) {
  return (
    <article className="rounded-3xl rounded-tl-lg border border-warn/25 bg-warn-soft px-5 py-4 sm:px-6">
      <p className="flex items-center gap-2 text-sm font-semibold text-warn">
        <SearchX className="h-4 w-4" /> Not covered by my sources
      </p>
      <div className="mt-2">
        <AnswerText text={m.content} sources={m.sources ?? []} />
      </div>
    </article>
  );
}

/** Renders the model's light Markdown (paragraphs, bullet/numbered lists, bold) with [n] citation chips. */
export function AnswerText({ text, sources }: { text: string; sources: Source[] }) {
  const byN = new Map(sources.map((s) => [s.n, s]));
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flush = () => {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    blocks.push(
      <Tag
        key={blocks.length}
        className={`my-3 space-y-1.5 pl-5 marker:text-accent ${list.ordered ? "list-decimal" : "list-disc"}`}
      >
        {list.items.map((item, i) => (
          <li key={i} className="pl-1">
            {inline(item, byN)}
          </li>
        ))}
      </Tag>,
    );
    list = null;
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      const ordered = !!numbered;
      if (list && list.ordered !== ordered) flush();
      list ??= { ordered, items: [] };
      list.items.push((bullet ?? numbered)![1]);
      continue;
    }
    flush();
    if (!line) continue;
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    blocks.push(
      heading ? (
        <p key={blocks.length} className="mt-4 mb-1 font-semibold">
          {inline(heading[1], byN)}
        </p>
      ) : (
        <p key={blocks.length} className="my-2.5 first:mt-0 last:mb-0">
          {inline(line, byN)}
        </p>
      ),
    );
  }
  flush();
  return <div className="text-[0.97rem] leading-7 text-text">{blocks}</div>;
}

// A word followed by one or more [n] citations and any trailing punctuation, e.g. "teeth [1][3]."
const CITED_WORD = /(\S*\s*(?:\[\d+\]\s*)*\[\d+\][.,;:!?)]*)/g;

function inline(text: string, byN: Map<number, Source>): ReactNode[] {
  let key = 0;
  const nodes: ReactNode[] = [];

  for (const segment of text.split(/(\*\*[^*]+\*\*)/g)) {
    if (!segment) continue;
    if (segment.length > 4 && segment.startsWith("**") && segment.endsWith("**")) {
      nodes.push(
        <strong key={key++} className="font-semibold">
          {segment.slice(2, -2)}
        </strong>,
      );
      continue;
    }

    // Keep each citation run glued to the word before it so a chip never wraps onto its own line.
    for (const part of segment.split(CITED_WORD)) {
      if (!part) continue;
      const m = part.match(/^(.*?)((?:\s*\[\d+\])+)([.,;:!?)]*)$/);
      if (!m) {
        nodes.push(<span key={key++}>{part}</span>);
        continue;
      }
      const [, word, run, punctuation] = m;
      nodes.push(
        <span key={key++} className="whitespace-nowrap">
          {word.trimEnd()}
          {[...run.matchAll(/\[(\d+)\]/g)].map(([raw, n], j) => {
            const src = byN.get(Number(n));
            return src ? <Cite key={j} source={src} /> : <span key={j}>{raw}</span>;
          })}
          {punctuation}
        </span>,
      );
    }
  }
  return nodes;
}

function Cite({ source: s }: { source: Source }) {
  return (
    <span className="group/cite relative inline-block">
      <a
        href={s.url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Source ${s.n}: ${s.title}`}
        className="ml-1 inline-flex h-5 min-w-5 -translate-y-0.5 items-center justify-center rounded-full bg-accent-soft px-1.5 text-[0.68rem] font-semibold tabular-nums leading-none text-accent-strong ring-1 ring-accent/15 transition hover:bg-accent hover:text-on-accent"
      >
        {s.n}
      </a>
      <span
        role="tooltip"
        // display:none until hovered, so hidden tooltips never widen the page; Tailwind v4's hover
        // variants only apply on hover-capable devices, so touch screens just follow the link.
        className="pointer-events-none absolute bottom-full left-1/2 z-40 mb-2 hidden w-64 max-w-[70vw] -translate-x-1/2 rounded-2xl border border-border bg-surface p-3 text-left leading-snug shadow-xl group-hover/cite:block group-hover/cite:animate-fade-up"
      >
        <PublisherBadge publisher={s.publisher} />
        <span className="mt-1.5 block text-sm font-semibold text-text">{s.title}</span>
        {s.section && <span className="mt-0.5 block text-xs text-muted">{s.section}</span>}
      </span>
    </span>
  );
}

function SourceList({ sources }: { sources: Source[] }) {
  const [showOthers, setShowOthers] = useState(false);
  const cited = sources.filter((s) => s.cited);
  const others = sources.filter((s) => !s.cited);
  if (!cited.length) return null;

  return (
    <div className="mt-5">
      <p className="mb-2.5 text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-muted">Sources</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {cited.map((s) => (
          <SourceCard key={s.n} source={s} />
        ))}
      </div>
      {others.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowOthers((v) => !v)}
            aria-expanded={showOthers}
            className="mt-2.5 inline-flex items-center gap-1 rounded-full py-1 text-xs font-medium text-muted hover:text-text"
          >
            <ChevronDown className={`h-3.5 w-3.5 transition ${showOthers ? "rotate-180" : ""}`} />
            {showOthers ? "Hide" : "Show"} {others.length} other retrieved passage{others.length > 1 ? "s" : ""}
          </button>
          {showOthers && (
            <div className="mt-2 grid gap-2 opacity-85 sm:grid-cols-2">
              {others.map((s) => (
                <SourceCard key={s.n} source={s} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SourceCard({ source: s }: { source: Source }) {
  const host = new URL(s.url).hostname.replace(/^www\./, "");
  return (
    <a
      href={s.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex min-w-0 items-start gap-3 rounded-2xl border border-border bg-surface-2 p-3 transition hover:-translate-y-px hover:border-accent/40 hover:shadow-card"
    >
      <span className="flex h-6 min-w-6 items-center justify-center rounded-full bg-accent-soft px-1 text-[0.7rem] font-semibold tabular-nums text-accent-strong">
        {s.n}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-text">{s.title}</span>
        <span className="block truncate text-xs text-muted">{s.section || "Overview"}</span>
        <span className="mt-1.5 flex items-center gap-1.5 text-[0.68rem] text-muted">
          <PublisherBadge publisher={s.publisher} />
          <span className="truncate">{host}</span>
        </span>
      </span>
      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted opacity-0 transition group-hover:opacity-100" />
    </a>
  );
}

function PublisherBadge({ publisher }: { publisher: string }) {
  return (
    <span className="inline-block rounded-md bg-subtle px-1.5 py-0.5 text-[0.6rem] font-bold uppercase tracking-wider text-muted">
      {publisher}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          // Clipboard unavailable (e.g. insecure context) — nothing to do.
        }
      }}
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium transition hover:bg-subtle hover:text-text"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-ok" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}
