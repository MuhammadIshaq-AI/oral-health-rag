"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import {
  ArrowUp,
  ArrowUpRight,
  Baby,
  Brush,
  Info,
  LoaderCircle,
  MapPin,
  MessageCircle,
  Microscope,
  Phone,
  Quote,
  RotateCcw,
  ShieldCheck,
  Smile,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { BRAND, telHref } from "@/lib/brand";
import type { ChatResponse, Message } from "@/lib/types";
import { AnswerCard, RefusalCard } from "./Answer";
import { BrandLogo } from "./BrandLogo";
import { ToothMark } from "./ToothMark";

const TOPICS = [
  { icon: Microscope, title: "About the practice", question: "What makes Scope Dental Practice different?" },
  { icon: Phone, title: "Contact us", question: "What's the best way to contact Scope Dental Practice?" },
  { icon: MessageCircle, title: "Appointments", question: "How can I book an appointment?" },
  { icon: Brush, title: "Everyday care", question: "How long should I brush my teeth, and should I rinse afterwards?" },
  { icon: Smile, title: "Gum health", question: "Why do my gums bleed when I brush?" },
  { icon: Baby, title: "Children's teeth", question: "When should I start brushing my baby's teeth?" },
];

const TRUST = [
  { icon: Microscope, label: "Microscope-enhanced care" },
  { icon: Quote, label: "Every answer cited" },
  { icon: ShieldCheck, label: "Says so when it doesn't know" },
];

const STEPS = [
  "Searching Scope Dental & NHS/WHO guidance",
  "Reading the most relevant passages",
  "Writing a cited answer",
];

type Health = { state: "checking" } | { state: "online" } | { state: "offline" };

const uid = () => Math.random().toString(36).slice(2);

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [health, setHealth] = useState<Health>({ state: "checking" });
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d: { ok: boolean }) => setHealth({ state: d.ok ? "online" : "offline" }))
      .catch(() => setHealth({ state: "offline" }));
  }, []);

  useEffect(() => {
    if (messages.length) bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  async function send(text: string, base: Message[] = messages) {
    const question = text.trim();
    if (!question || pending) return;

    const history = base.filter((m) => !m.error).map(({ role, content }) => ({ role, content }));
    const userMsg: Message = { id: uid(), role: "user", content: question };
    setMessages([...base, userMsg]);
    setInput("");
    setPending(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question, history }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${res.status}).`);
      }
      const answer = data as ChatResponse;
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: "assistant",
          content: answer.answer,
          sources: answer.sources,
          refused: answer.refused,
          latency: answer.latency_s,
        },
      ]);
      setHealth({ state: "online" });
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: "assistant",
          content: err instanceof Error ? err.message : "Something went wrong.",
          error: true,
          retry: { question, userId: userMsg.id },
        },
      ]);
    } finally {
      setPending(false);
      inputRef.current?.focus();
    }
  }

  function retry(failed: Message) {
    if (!failed.retry) return;
    const base = messages.filter((m) => m.id !== failed.id && m.id !== failed.retry!.userId);
    send(failed.retry.question, base);
  }

  const empty = messages.length === 0;

  return (
    <div className="relative flex min-h-dvh flex-col overflow-x-clip">
      <div aria-hidden className="app-backdrop pointer-events-none fixed inset-0 -z-10" />

      <Header
        health={health}
        showReset={!empty}
        resetDisabled={pending}
        onReset={() => {
          setMessages([]);
          inputRef.current?.focus();
        }}
      />

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 sm:px-6">
        {empty ? (
          <Hero onAsk={(q) => send(q)} disabled={pending} />
        ) : (
          <div className="space-y-6 pt-6 pb-4" aria-live="polite">
            {messages.map((m) =>
              m.role === "user" ? (
                <UserBubble key={m.id} text={m.content} />
              ) : (
                <AssistantRow key={m.id}>
                  {m.error ? (
                    <ErrorCard message={m} onRetry={() => retry(m)} disabled={pending} />
                  ) : m.refused ? (
                    <RefusalCard message={m} />
                  ) : (
                    <AnswerCard message={m} />
                  )}
                </AssistantRow>
              ),
            )}
            {pending && <Thinking />}
            <div ref={bottomRef} />
          </div>
        )}
      </main>

      <Composer
        value={input}
        onChange={setInput}
        onSubmit={() => send(input)}
        pending={pending}
        inputRef={inputRef}
      />
    </div>
  );
}

function Header({
  health,
  showReset,
  resetDisabled,
  onReset,
}: {
  health: Health;
  showReset: boolean;
  resetDisabled: boolean;
  onReset: () => void;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-bg/80 pt-[env(safe-area-inset-top)] backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-3xl items-center gap-3 px-4 sm:px-6">
        <BrandLogo />
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-[1.15rem] font-semibold leading-none tracking-tight">
            {BRAND.name}
          </p>
          <StatusLine health={health} />
        </div>
        <a
          href={BRAND.whatsapp}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Book on WhatsApp"
          className="inline-flex items-center gap-1.5 rounded-full bg-accent px-3 py-1.5 text-sm font-semibold text-on-accent shadow-card transition hover:opacity-90"
        >
          <MessageCircle className="h-4 w-4" />
          <span className="hidden sm:inline">Book on WhatsApp</span>
        </a>
        {showReset && (
          <button
            type="button"
            onClick={onReset}
            disabled={resetDisabled}
            aria-label="New chat"
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-sm font-medium text-muted shadow-card transition hover:border-border-strong hover:text-text disabled:opacity-50"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">New chat</span>
          </button>
        )}
      </div>
    </header>
  );
}

function StatusLine({ health }: { health: Health }) {
  const { dot, text } = {
    checking: { dot: "bg-muted", text: "Connecting…" },
    online: { dot: "bg-ok", text: `Patient assistant · ${BRAND.city}` },
    offline: { dot: "bg-warn", text: "Assistant unavailable right now" },
  }[health.state];

  return (
    <span className="mt-1 flex items-center gap-1.5 text-xs text-muted">
      <span className="relative flex h-2 w-2 shrink-0">
        {health.state === "online" && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-50" />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${dot}`} />
      </span>
      <span className="truncate">{text}</span>
    </span>
  );
}

function Hero({ onAsk, disabled }: { onAsk: (q: string) => void; disabled: boolean }) {
  return (
    <section className="pt-10 pb-6 sm:pt-16">
      <div className="animate-fade-up text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-accent/30 bg-accent-soft/80 px-3 py-1 text-xs font-medium tracking-wide text-accent-strong">
          <Sparkles className="h-3.5 w-3.5" />
          {BRAND.tagline} · {BRAND.city}
        </span>
        <h1 className="mx-auto mt-5 max-w-xl font-display text-[2.6rem] font-medium leading-[1.05] tracking-tight text-balance sm:text-[3.6rem]">
          How can we help your <em className="italic text-accent">smile</em> today?
        </h1>
        <p className="mx-auto mt-4 max-w-lg text-pretty text-[1rem] leading-relaxed text-muted">
          Ask about visiting {BRAND.name}, booking an appointment, or everyday questions about teeth and
          gums. Answers come from the practice&apos;s own information and trusted NHS &amp; WHO guidance, with
          sources you can check.
        </p>
        <ul className="mt-6 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm text-muted">
          {TRUST.map(({ icon: Icon, label }) => (
            <li key={label} className="inline-flex items-center gap-1.5">
              <Icon className="h-4 w-4 text-accent" />
              {label}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-10 grid gap-3 sm:grid-cols-2">
        {TOPICS.map((t, i) => (
          <button
            key={t.title}
            type="button"
            onClick={() => onAsk(t.question)}
            disabled={disabled}
            style={{ animationDelay: `${120 + i * 60}ms` }}
            className="group flex animate-fade-up items-start gap-3.5 rounded-2xl border border-border bg-surface/85 p-4 text-left shadow-card backdrop-blur transition hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent-strong ring-1 ring-accent/20">
              <t.icon className="h-5 w-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-muted">
                {t.title}
              </span>
              <span className="mt-1 block text-[0.93rem] font-medium leading-snug text-text">{t.question}</span>
            </span>
            <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-muted opacity-0 transition group-hover:text-accent group-hover:opacity-100" />
          </button>
        ))}
      </div>

      <ContactCard />

      <p className="mx-auto mt-10 max-w-xl text-center text-xs leading-relaxed text-muted">
        Practice information from{" "}
        <a className="underline decoration-border-strong underline-offset-2 hover:text-text" href={BRAND.website} target="_blank" rel="noopener noreferrer">
          scopedental.pk
        </a>
        . General dental guidance: NHS website content, licensed under the{" "}
        <a
          className="underline decoration-border-strong underline-offset-2 hover:text-text"
          href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Open Government Licence v3.0
        </a>
        , and WHO fact sheets, © World Health Organization,{" "}
        <a
          className="underline decoration-border-strong underline-offset-2 hover:text-text"
          href="https://creativecommons.org/licenses/by-nc-sa/3.0/igo/"
          target="_blank"
          rel="noopener noreferrer"
        >
          CC BY-NC-SA 3.0 IGO
        </a>
        . Not endorsed by the NHS or WHO. This assistant gives general information and does not replace a
        consultation.
      </p>
    </section>
  );
}

function ContactCard() {
  const button =
    "inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3.5 py-2 text-sm font-medium text-text shadow-card transition hover:border-accent/50";
  return (
    <div
      className="mt-8 flex animate-fade-up flex-col items-center gap-4 rounded-2xl border border-border bg-surface/85 p-5 text-center shadow-card backdrop-blur sm:flex-row sm:justify-between sm:text-left"
      style={{ animationDelay: "500ms" }}
    >
      <div className="min-w-0">
        <p className="font-display text-xl font-medium">Prefer to speak to us?</p>
        <p className="mt-0.5 text-sm text-muted">
          {BRAND.fullName}
          {BRAND.address && ` · ${BRAND.address}`}
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        <a href={BRAND.whatsapp} target="_blank" rel="noopener noreferrer" className={button}>
          <MessageCircle className="h-4 w-4 text-accent" /> WhatsApp
        </a>
        <a href={telHref(BRAND.phones[0])} className={button}>
          <Phone className="h-4 w-4 text-accent" /> {BRAND.phones[0]}
        </a>
        <a href={BRAND.mapsUrl} target="_blank" rel="noopener noreferrer" className={button}>
          <MapPin className="h-4 w-4 text-accent" /> Directions
        </a>
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex animate-fade-up justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-3xl rounded-br-lg bg-linear-to-br from-accent to-accent-strong px-4.5 py-3 text-[0.96rem] leading-relaxed text-on-accent shadow-card dark:from-accent dark:to-[#a98642]">
        {text}
      </div>
    </div>
  );
}

function AssistantRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex animate-fade-up gap-3">
      <ToothMark className="mt-1 hidden h-8 w-8 sm:inline-flex" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function ErrorCard({ message, onRetry, disabled }: { message: Message; onRetry: () => void; disabled: boolean }) {
  return (
    <div role="alert" className="rounded-3xl rounded-tl-lg border border-danger/25 bg-danger-soft px-5 py-4 text-sm">
      <p className="flex items-center gap-2 font-semibold text-danger">
        <TriangleAlert className="h-4 w-4" /> Couldn&apos;t get an answer
      </p>
      <p className="mt-1 text-text/80">{message.content}</p>
      {message.retry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={disabled}
          className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-text shadow-card transition hover:border-border-strong disabled:opacity-50"
        >
          <RotateCcw className="h-3.5 w-3.5" /> Try again
        </button>
      )}
    </div>
  );
}

function Thinking() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 1800);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex animate-fade-up gap-3" role="status">
      <ToothMark className="mt-1 hidden h-8 w-8 sm:inline-flex" pulse />
      <div className="min-w-0 flex-1 rounded-3xl rounded-tl-lg border border-border bg-surface px-5 py-4 shadow-card sm:px-6">
        <p className="flex items-center gap-2 text-sm font-medium text-muted">
          <LoaderCircle className="h-4 w-4 animate-spin text-accent" />
          {STEPS[step]}…
        </p>
        <div className="mt-4 space-y-2.5" aria-hidden>
          <div className="shimmer h-2.5 w-11/12 rounded-full" />
          <div className="shimmer h-2.5 w-4/5 rounded-full" />
          <div className="shimmer h-2.5 w-3/5 rounded-full" />
        </div>
      </div>
    </div>
  );
}

function Composer({
  value,
  onChange,
  onSubmit,
  pending,
  inputRef,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  pending: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}) {
  return (
    <div className="sticky bottom-0 z-20">
      <div aria-hidden className="pointer-events-none h-8 bg-linear-to-t from-bg to-transparent" />
      <div className="bg-bg pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit();
          }}
          className="mx-auto max-w-3xl px-4 sm:px-6"
        >
          <div className="flex items-end gap-2 rounded-[1.75rem] border border-border bg-surface p-2 pl-5 shadow-card transition focus-within:border-accent/60 focus-within:ring-4 focus-within:ring-accent/15">
            <label htmlFor="question" className="sr-only">
              Your question
            </label>
            <textarea
              id="question"
              ref={inputRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSubmit();
                }
              }}
              rows={1}
              maxLength={1000}
              placeholder="Ask about your visit, teeth or gums…"
              className="max-h-40 min-h-11 flex-1 resize-none bg-transparent py-2.5 text-[0.96rem] leading-6 outline-none placeholder:text-muted/80"
            />
            <button
              type="submit"
              disabled={pending || !value.trim()}
              aria-label="Send question"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent text-on-accent shadow-sm transition hover:opacity-90 active:scale-95 disabled:bg-subtle disabled:text-muted disabled:shadow-none"
            >
              {pending ? <LoaderCircle className="h-5 w-5 animate-spin" /> : <ArrowUp className="h-5 w-5" />}
            </button>
          </div>
          <p className="mt-2 flex items-center justify-center gap-1.5 text-center text-[0.7rem] text-muted">
            <Info className="h-3 w-3 shrink-0" />
            General information, not a diagnosis. For urgent dental problems call {BRAND.phones[0]}.
          </p>
        </form>
      </div>
    </div>
  );
}
