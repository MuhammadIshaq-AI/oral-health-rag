/**
 * Typed client for the DentalCare AU FastAPI backend.
 * All requests are same-origin (`/api/...`); in development Vite proxies them
 * to http://localhost:8000.
 */

export type Role = 'user' | 'assistant'
export type Modality = 'text' | 'voice' | 'voice_upload'
export type Severity = 'none' | 'info' | 'urgent' | 'emergency' | 'crisis'

export interface HistoryTurn {
  role: Role
  content: string
}

export interface SttMeta {
  transcript: string
  language: string | null
  language_probability: number | null
  confidence: number | null
  duration_s: number | null
  latency_ms: number | null
  model: string | null
}

export interface ChatRequest {
  session_id: string
  message: string
  history: HistoryTurn[]
  modality: Modality
  stt?: SttMeta
}

export interface Source {
  n: number
  chunk_id: string
  source_org: string
  page_title: string
  section: string
  url: string
  text: string
  retrieved_at: string
  jurisdiction: string
  secondary: boolean
  cited: boolean
  score: number
}

export interface TriageAction {
  label: string
  href: string
  kind: 'emergency' | 'crisis' | 'info' | string
}

export interface Triage {
  label: string
  severity: Severity
  title: string | null
  message: string | null
  actions: TriageAction[]
  halted: boolean
}

export interface ChatResponse {
  turn_id: string
  answer: string
  sources: Source[]
  refused: boolean
  triage: Triage
  rewritten_query: string | null
  latency_ms: Record<string, number>
  model: string
  corpus_version: string
  config_hash: string
}

export interface Health {
  status: 'ok' | 'no_index' | string
  model: string
  provider: string
  local_only: boolean
  corpus_version: string | null
  n_chunks: number
  vector_store: string | null
  retrieval_mode: string
  config_name: string
  config_hash: string
  prompt_version: string
  tts_enabled: boolean
  whisper_model: string
}

export interface SttSegment {
  start: number
  end: number
  text: string
  avg_logprob: number
  no_speech_prob: number
  confidence: number
}

export interface SttResult {
  text: string
  language: string | null
  language_probability: number | null
  duration_s: number | null
  confidence: number | null
  segments: SttSegment[]
  model: string | null
  latency_ms: number | null
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: string | null

  constructor(status: number, message: string, detail: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''

async function readDetail(res: Response): Promise<string | null> {
  try {
    const body: unknown = await res.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      return JSON.stringify(detail)
    }
  } catch {
    // Body was not JSON.
  }
  return null
}

async function request(path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<Response> {
  const { timeoutMs = 30_000, signal, ...rest } = init
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  const onAbort = () => controller.abort()
  signal?.addEventListener('abort', onAbort)
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { ...rest, signal: controller.signal })
  } catch (err) {
    if (signal?.aborted) throw err
    if (controller.signal.aborted) {
      throw new ApiError(0, 'The request took too long. Please try again.')
    }
    throw new ApiError(0, 'Could not reach the DentalCare AU service. Please check your connection.')
  } finally {
    window.clearTimeout(timer)
    signal?.removeEventListener('abort', onAbort)
  }
  if (!res.ok) {
    const detail = await readDetail(res)
    throw new ApiError(res.status, messageForStatus(res.status), detail)
  }
  return res
}

function messageForStatus(status: number): string {
  if (status === 422) return 'Sorry, that message could not be processed. Please try rephrasing it.'
  if (status === 503) return 'The service is not ready right now. Please try again in a moment.'
  if (status >= 500) return 'Something went wrong on our side. Please try again.'
  return `The request failed (error ${status}).`
}

async function postJson<T>(path: string, body: unknown, timeoutMs?: number, signal?: AbortSignal): Promise<T> {
  const res = await request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    timeoutMs,
    signal,
  })
  return (await res.json()) as T
}

export async function getHealth(): Promise<Health> {
  const res = await request('/api/health', { timeoutMs: 10_000 })
  return (await res.json()) as Health
}

export async function createSession(): Promise<string> {
  const data = await postJson<{ session_id: string }>('/api/session', {})
  return data.session_id
}

export async function postConsent(sessionId: string, consent: boolean): Promise<void> {
  await postJson<{ ok: boolean }>('/api/consent', { session_id: sessionId, consent })
}

export async function postChat(body: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  return postJson<ChatResponse>('/api/chat', body, 180_000, signal)
}

export async function transcribeFile(file: Blob, filename = 'audio'): Promise<SttResult> {
  const form = new FormData()
  form.append('file', file, filename)
  const res = await request('/api/stt', { method: 'POST', body: form, timeoutMs: 180_000 })
  return (await res.json()) as SttResult
}

/** Request speech audio for `text`. Resolves to a WAV blob. */
export async function synthesize(text: string, signal?: AbortSignal): Promise<Blob> {
  const res = await request('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    timeoutMs: 120_000,
    signal,
  })
  return res.blob()
}

export function sttStreamUrl(): string {
  if (API_BASE) {
    const url = new URL(`${API_BASE}/api/stt/stream`, window.location.href)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    return url.toString()
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/stt/stream`
}

export function sttToMeta(result: SttResult): SttMeta {
  return {
    transcript: result.text,
    language: result.language ?? null,
    language_probability: result.language_probability ?? null,
    confidence: result.confidence ?? null,
    duration_s: result.duration_s ?? null,
    latency_ms: result.latency_ms ?? null,
    model: result.model ?? null,
  }
}
