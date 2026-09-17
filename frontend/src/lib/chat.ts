import type { ChatResponse, HistoryTurn, Modality, SttMeta } from '../api'
import { toSpeechText } from './markdown'

export interface UserMessage {
  id: string
  role: 'user'
  content: string
  modality: Modality
}

export interface AssistantMessage {
  id: string
  role: 'assistant'
  response: ChatResponse
}

export interface ErrorMessage {
  id: string
  role: 'error'
  message: string
  /** What to resend when the user taps Retry. */
  retry: { text: string; modality: Modality; stt?: SttMeta }
}

export type ChatMessage = UserMessage | AssistantMessage | ErrorMessage

let counter = 0
export function newId(prefix: string): string {
  counter += 1
  return `${prefix}-${Date.now().toString(36)}-${counter}`
}

const MAX_HISTORY = 12
const MAX_CONTENT = 6000

/** Last ~12 user/assistant turns in the shape /api/chat expects. */
export function buildHistory(messages: ChatMessage[]): HistoryTurn[] {
  const turns: HistoryTurn[] = []
  for (const m of messages) {
    if (m.role === 'user') {
      turns.push({ role: 'user', content: m.content.slice(0, MAX_CONTENT) })
    } else if (m.role === 'assistant') {
      const content = m.response.answer.trim() || m.response.triage.message?.trim() || ''
      if (content) turns.push({ role: 'assistant', content: content.slice(0, MAX_CONTENT) })
    }
  }
  return turns.slice(-MAX_HISTORY)
}

/** Text read aloud for an assistant turn (safety message first). */
export function speechSourceText(response: ChatResponse): string {
  const parts: string[] = []
  const { triage } = response
  if (triage.severity !== 'none') {
    if (triage.title) parts.push(triage.title)
    if (triage.message) parts.push(triage.message)
  }
  if (response.answer.trim()) parts.push(response.answer)
  return toSpeechText(parts.join('\n\n'))
}
