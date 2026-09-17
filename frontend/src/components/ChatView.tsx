import { useEffect, useRef } from 'react'
import type { TtsControls } from '../hooks/useTts'
import type { ChatMessage } from '../lib/chat'
import { MessageBubble } from './MessageBubble'
import { StarterQuestions } from './StarterQuestions'
import { ThinkingIndicator } from './ThinkingIndicator'

interface ChatViewProps {
  messages: ChatMessage[]
  waiting: boolean
  tts: TtsControls
  onRetry: (id: string) => void
  onPickStarter: (question: string) => void
  statusNotice: string | null
}

export function ChatView({ messages, waiting, tts, onRetry, onPickStarter, statusNotice }: ChatViewProps) {
  const listRef = useRef<HTMLOListElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const last = messages[messages.length - 1]
  const lastId = last?.id
  const lastRole = last?.role

  useEffect(() => {
    if (!lastId && !waiting) return
    const behavior: ScrollBehavior = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      ? 'auto'
      : 'smooth'
    if (!waiting && lastRole !== 'user') {
      // A new answer: show its beginning so long answers are read from the top.
      const item = listRef.current?.querySelector<HTMLElement>(`[data-message-id="${lastId}"]`)
      if (item) {
        item.scrollIntoView({ block: 'start', behavior })
        return
      }
    }
    endRef.current?.scrollIntoView({ block: 'end', behavior })
  }, [lastId, lastRole, waiting])

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-3 sm:py-4">
      {statusNotice ? (
        <p
          role="status"
          className="mb-4 rounded-xl border-2 border-amber-600 bg-amber-50 p-3 text-amber-950 dark:border-amber-400 dark:bg-amber-950 dark:text-amber-50"
        >
          {statusNotice}
        </p>
      ) : null}

      {messages.length === 0 ? (
        <StarterQuestions onPick={onPickStarter} disabled={waiting} />
      ) : (
        <ol ref={listRef} aria-label="Conversation" className="space-y-4">
          {messages.map((m) => (
            <li key={m.id} data-message-id={m.id} className="scroll-mt-4">
              <MessageBubble message={m} tts={tts} busy={waiting} onRetry={onRetry} />
            </li>
          ))}
        </ol>
      )}

      {waiting ? (
        <div className="mt-5">
          <ThinkingIndicator />
        </div>
      ) : null}
      <div ref={endRef} />
    </div>
  )
}
