import { AlertCircle, Loader2, SendHorizontal, Upload, X } from 'lucide-react'
import { useLayoutEffect, useRef, type ChangeEvent, type FormEvent, type KeyboardEvent, type RefObject } from 'react'
import type { PushToTalkControls } from '../hooks/usePushToTalk'
import { PushToTalk } from './PushToTalk'
import { Waveform } from './Waveform'

export const MAX_MESSAGE_LENGTH = 2000

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  /** True while waiting for an answer. */
  waiting: boolean
  note: string | null
  onDismissNote: () => void
  ptt: PushToTalkControls
  uploading: boolean
  uploadError: string | null
  onDismissUploadError: () => void
  onUpload: (file: File) => void
  textareaRef: RefObject<HTMLTextAreaElement>
}

export function Composer({
  value,
  onChange,
  onSubmit,
  waiting,
  note,
  onDismissNote,
  ptt,
  uploading,
  uploadError,
  onDismissUploadError,
  onUpload,
  textareaRef,
}: ComposerProps) {
  const fileRef = useRef<HTMLInputElement>(null)
  const voiceBusy = ptt.status === 'starting' || ptt.status === 'recording' || ptt.status === 'finishing'
  const canSend = !waiting && !voiceBusy && !uploading && value.trim().length > 0

  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const max = Math.max(160, Math.round(window.innerHeight * 0.35))
    el.style.height = `${Math.min(el.scrollHeight + 2, max)}px`
    el.style.overflowY = el.scrollHeight + 2 > max ? 'auto' : 'hidden'
  }, [value, textareaRef])

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (canSend) onSubmit()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) onUpload(file)
  }

  const showVoicePanel = voiceBusy || ptt.status === 'error' || uploading || Boolean(uploadError)
  const remaining = MAX_MESSAGE_LENGTH - value.length

  return (
    <form onSubmit={submit} aria-label="Ask a question" className="space-y-3">
      {showVoicePanel ? (
        <div className="rounded-2xl border-2 border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
          {ptt.status === 'error' && ptt.error ? (
            <div role="alert" className="flex items-start gap-3 text-rose-900 dark:text-rose-100">
              <AlertCircle aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0" />
              <p className="flex-1">{ptt.error}</p>
              <DismissButton label="Dismiss message" onClick={ptt.clearError} />
            </div>
          ) : null}

          {uploadError ? (
            <div role="alert" className="flex items-start gap-3 text-rose-900 dark:text-rose-100">
              <AlertCircle aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0" />
              <p className="flex-1">{uploadError}</p>
              <DismissButton label="Dismiss message" onClick={onDismissUploadError} />
            </div>
          ) : null}

          {ptt.status === 'recording' ? <Waveform analyser={ptt.analyser} /> : null}

          <div aria-live="polite" className="min-h-0">
            {ptt.status === 'starting' ? <p className="font-semibold">Starting the microphone…</p> : null}
            {ptt.status === 'recording' ? (
              <p className="font-semibold text-red-800 dark:text-red-300">Listening… release or tap the button to finish.</p>
            ) : null}
            {ptt.status === 'finishing' ? (
              <p className="flex items-center gap-2 font-semibold">
                <Loader2 aria-hidden="true" className="h-5 w-5 motion-safe:animate-spin" />
                Working out what you said…
              </p>
            ) : null}
            {uploading ? (
              <p className="flex items-center gap-2 font-semibold">
                <Loader2 aria-hidden="true" className="h-5 w-5 motion-safe:animate-spin" />
                Transcribing your audio file…
              </p>
            ) : null}
            {voiceBusy && ptt.partial ? (
              <p className="mt-1 text-lg text-slate-900 dark:text-slate-100">
                <span className="sr-only">So far we heard: </span>
                &ldquo;{ptt.partial}&rdquo;
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {note ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-xl border-2 border-amber-600 bg-amber-50 p-3 text-amber-950 dark:border-amber-400 dark:bg-amber-950 dark:text-amber-50"
        >
          <AlertCircle aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0" />
          <p className="flex-1">{note}</p>
          <DismissButton label="Dismiss note" onClick={onDismissNote} />
        </div>
      ) : null}

      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <label htmlFor="question-input" className="sr-only">
            Your question
          </label>
          <textarea
            id="question-input"
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value.slice(0, MAX_MESSAGE_LENGTH))}
            onKeyDown={onKeyDown}
            rows={1}
            maxLength={MAX_MESSAGE_LENGTH}
            placeholder="Type your question…"
            aria-describedby="composer-hint"
            enterKeyHint="send"
            className="block min-h-14 w-full resize-none rounded-2xl border-2 border-slate-400 bg-white px-4 py-3 text-[max(18px,1rem)] leading-snug text-slate-900 placeholder:text-slate-600 focus:border-teal-700 dark:border-slate-500 dark:bg-slate-900 dark:text-slate-50 dark:placeholder:text-slate-400 dark:focus:border-teal-300"
          />
        </div>
        <button
          type="submit"
          disabled={!canSend}
          aria-label={waiting ? 'Waiting for the answer' : 'Send question'}
          className="inline-flex h-14 min-h-12 w-14 min-w-12 shrink-0 items-center justify-center rounded-2xl bg-teal-800 text-white shadow-sm hover:bg-teal-900 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600 dark:bg-teal-300 dark:text-slate-950 dark:hover:bg-teal-200 dark:disabled:bg-slate-700 dark:disabled:text-slate-300"
        >
          {waiting ? (
            <Loader2 aria-hidden="true" className="h-7 w-7 motion-safe:animate-spin" />
          ) : (
            <SendHorizontal aria-hidden="true" className="h-7 w-7" />
          )}
        </button>
        <PushToTalk
          status={ptt.status}
          disabled={waiting || uploading}
          onStart={ptt.start}
          onStop={ptt.stop}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={waiting || uploading || voiceBusy}
          className="inline-flex min-h-12 items-center gap-2 rounded-xl px-2 text-base font-semibold text-teal-800 underline-offset-4 hover:underline disabled:cursor-not-allowed disabled:opacity-60 dark:text-teal-300"
        >
          <Upload aria-hidden="true" className="h-5 w-5" />
          Upload audio
        </button>
        <input ref={fileRef} type="file" accept="audio/*" className="hidden" onChange={onFile} tabIndex={-1} />
        <p id="composer-hint" className="text-sm text-slate-700 dark:text-slate-300">
          {remaining < 200
            ? `${remaining} characters left`
            : 'Enter to send · Shift+Enter for a new line · Hold the mic to talk'}
        </p>
      </div>
    </form>
  )
}

function DismissButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="-m-2 inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full hover:bg-black/5 dark:hover:bg-white/10"
    >
      <X aria-hidden="true" className="h-6 w-6" />
    </button>
  )
}
