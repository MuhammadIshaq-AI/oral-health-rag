import { Info, Loader2, Mic, Square, Volume2 } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
import type { TtsControls } from '../hooks/useTts'
import { speechSourceText, type ChatMessage } from '../lib/chat'
import { AnswerText } from './AnswerText'
import { CitationPanel } from './CitationChip'
import { ErrorCard } from './ErrorCard'
import { SourceList } from './SourceList'
import { TriageAlert } from './TriageAlert'

interface MessageBubbleProps {
  message: ChatMessage
  tts: TtsControls
  busy: boolean
  onRetry: (id: string) => void
}

export function MessageBubble({ message, tts, busy, onRetry }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[88%] rounded-2xl rounded-br-md bg-gradient-to-br from-teal-700 to-teal-800 px-4 py-3 text-white shadow-md shadow-teal-900/15 dark:from-teal-600 dark:to-teal-700">
          <h2 className="sr-only">You asked</h2>
          {message.modality !== 'text' ? (
            <p className="mb-1 flex items-center gap-1.5 text-sm text-teal-50">
              <Mic aria-hidden="true" className="h-4 w-4" />
              {message.modality === 'voice' ? 'Spoken question' : 'From audio file'}
            </p>
          ) : null}
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>
      </div>
    )
  }

  if (message.role === 'error') {
    return (
      <div className="flex justify-start">
        <div className="w-full max-w-[94%]">
          <ErrorCard message={message.message} onRetry={() => onRetry(message.id)} disabled={busy} />
        </div>
      </div>
    )
  }

  return <AssistantBubble message={message} tts={tts} />
}

function AssistantBubble({ message, tts }: { message: Extract<ChatMessage, { role: 'assistant' }>; tts: TtsControls }) {
  const { response } = message
  const [openCitation, setOpenCitation] = useState<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const panelId = `${message.id}-source`
  const openSource = openCitation === null ? null : response.sources.find((s) => s.n === openCitation) ?? null

  const toggle = useCallback((n: number) => setOpenCitation((prev) => (prev === n ? null : n)), [])
  const close = useCallback(() => {
    const n = openCitation
    setOpenCitation(null)
    // Return focus to a control for that source so keyboard users keep their place.
    if (n !== null) {
      containerRef.current?.querySelector<HTMLButtonElement>(`button[data-citation="${n}"]`)?.focus()
    }
  }, [openCitation])

  const hasAnswer = response.answer.trim().length > 0
  const isActive = tts.activeId === message.id
  const speechText = speechSourceText(response)

  return (
    <div className="flex justify-start">
      <article
        ref={containerRef}
        aria-label="DentalCare AU answer"
        className="surface-card w-full max-w-[94%] space-y-3 rounded-bl-md px-4 py-3 text-slate-900 dark:text-slate-100"
      >
        <TriageAlert triage={response.triage} />

        {hasAnswer && response.refused ? (
          <div className="flex items-start gap-3 rounded-xl bg-sky-50 p-4 text-sky-950 dark:bg-sky-950 dark:text-sky-50">
            <Info aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0" />
            <AnswerText text={response.answer} className="min-w-0 flex-1" />
          </div>
        ) : null}

        {hasAnswer && !response.refused ? (
          <div>
            <AnswerText
              text={response.answer}
              sources={response.sources}
              openCitation={openCitation}
              panelId={panelId}
              onToggleCitation={toggle}
            />
            {openSource ? <CitationPanel source={openSource} id={panelId} onClose={close} /> : null}
            <SourceList sources={response.sources} openCitation={openCitation} panelId={panelId} onToggle={toggle} />
          </div>
        ) : null}

        {tts.available && speechText.trim() ? (
          <div>
            {isActive ? (
              <button
                type="button"
                onClick={tts.stop}
                className="inline-flex min-h-12 items-center gap-2 rounded-xl border-2 border-teal-800 bg-teal-800 px-4 font-semibold text-white hover:bg-teal-900 dark:border-teal-300 dark:bg-teal-300 dark:text-slate-950"
              >
                {tts.status === 'loading' ? (
                  <Loader2 aria-hidden="true" className="h-5 w-5 motion-safe:animate-spin" />
                ) : (
                  <Square aria-hidden="true" className="h-5 w-5" />
                )}
                {tts.status === 'loading' ? 'Preparing audio… Stop' : 'Stop reading'}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => tts.speak(message.id, speechText)}
                className="inline-flex min-h-12 items-center gap-2 rounded-xl border-2 border-teal-800 px-4 font-semibold text-teal-900 hover:bg-teal-50 dark:border-teal-300 dark:text-teal-100 dark:hover:bg-slate-800"
              >
                <Volume2 aria-hidden="true" className="h-5 w-5" />
                Listen
              </button>
            )}
          </div>
        ) : null}
      </article>
    </div>
  )
}
