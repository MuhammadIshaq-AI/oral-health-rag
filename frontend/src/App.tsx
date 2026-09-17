import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  createSession,
  getHealth,
  postChat,
  postConsent,
  sttToMeta,
  transcribeFile,
  type Health,
  type Modality,
  type SttMeta,
  type SttResult,
} from './api'
import { ChatView } from './components/ChatView'
import { Composer, MAX_MESSAGE_LENGTH } from './components/Composer'
import { ConsentGate } from './components/ConsentGate'
import { DisclaimerBanner } from './components/DisclaimerBanner'
import type { FontSize } from './components/FontSizeControl'
import { Header } from './components/Header'
import { useLocalStorage } from './hooks/useLocalStorage'
import { usePushToTalk } from './hooks/usePushToTalk'
import { useTts } from './hooks/useTts'
import { buildHistory, newId, speechSourceText, type ChatMessage } from './lib/chat'

interface ConsentRecord {
  sessionId: string | null
  consent: boolean
  /** Whether the backend has recorded this decision for this session. */
  synced: boolean
  decidedAt: string
}

const CONSENT_KEY = 'dentalcare-au.consent.v1'
const FONT_KEY = 'dentalcare-au.font-size'
const READ_ALOUD_KEY = 'dentalcare-au.read-aloud'

const LOW_CONFIDENCE = 0.5
const FONT_CLASSES: Record<FontSize, string> = {
  standard: 'fs-standard',
  large: 'fs-large',
  xlarge: 'fs-xlarge',
}

function isFontSize(v: unknown): v is FontSize {
  return v === 'standard' || v === 'large' || v === 'xlarge'
}
function isBoolean(v: unknown): v is boolean {
  return typeof v === 'boolean'
}
function isConsentRecord(v: unknown): v is ConsentRecord | null {
  if (v === null) return true
  if (!v || typeof v !== 'object') return false
  const r = v as Record<string, unknown>
  return (
    (r.sessionId === null || typeof r.sessionId === 'string') &&
    typeof r.consent === 'boolean' &&
    typeof r.synced === 'boolean'
  )
}

function errorText(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.message
  return fallback
}

export default function App() {
  const [fontSize, setFontSize] = useLocalStorage<FontSize>(FONT_KEY, 'standard', isFontSize)
  const [autoRead, setAutoRead] = useLocalStorage<boolean>(READ_ALOUD_KEY, false, isBoolean)
  const [consentRecord, setConsentRecord] = useLocalStorage<ConsentRecord | null>(CONSENT_KEY, null, isConsentRecord)

  const [health, setHealth] = useState<Health | null>(null)
  const [consentOpen, setConsentOpen] = useState(() => consentRecord === null)
  const [consentSaving, setConsentSaving] = useState(false)
  const [consentError, setConsentError] = useState<string | null>(null)
  const [syncNotice, setSyncNotice] = useState<string | null>(null)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [waiting, setWaiting] = useState(false)
  const [draft, setDraft] = useState('')
  const [note, setNote] = useState<string | null>(null)
  const [pendingStt, setPendingStt] = useState<{ meta: SttMeta; modality: Modality } | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const tts = useTts(health?.tts_enabled === true)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Refs mirror state for use inside async callbacks.
  const messagesRef = useRef(messages)
  const consentRef = useRef(consentRecord)
  const waitingRef = useRef(false)
  const autoReadRef = useRef(autoRead)
  const ttsAvailableRef = useRef(tts.available)
  const seqRef = useRef(0)
  useEffect(() => {
    messagesRef.current = messages
  }, [messages])
  useEffect(() => {
    consentRef.current = consentRecord
  }, [consentRecord])
  useEffect(() => {
    autoReadRef.current = autoRead
    ttsAvailableRef.current = tts.available
  }, [autoRead, tts.available])

  // Apply the chosen text size to <html> so every rem-based size scales.
  useEffect(() => {
    const root = document.documentElement
    Object.values(FONT_CLASSES).forEach((c) => root.classList.remove(c))
    root.classList.add(FONT_CLASSES[fontSize])
  }, [fontSize])

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((h) => {
        if (!cancelled) setHealth(h)
      })
      .catch(() => {
        if (!cancelled) setHealth(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const saveConsent = useCallback(
    (record: ConsentRecord) => {
      consentRef.current = record
      setConsentRecord(record)
    },
    [setConsentRecord],
  )

  /** Returns a session id, creating one and syncing consent if needed. */
  const ensureSession = useCallback(async (): Promise<string> => {
    const record = consentRef.current
    let sessionId = record?.sessionId ?? null
    if (!sessionId) sessionId = await createSession()
    if (record && (!record.synced || record.sessionId !== sessionId)) {
      let synced = false
      try {
        await postConsent(sessionId, record.consent)
        synced = true
        setSyncNotice(null)
      } catch {
        synced = false
      }
      saveConsent({ ...record, sessionId, synced })
    }
    return sessionId
  }, [saveConsent])

  const decideConsent = useCallback(
    async (consent: boolean) => {
      setConsentSaving(true)
      setConsentError(null)
      const previous = consentRef.current
      let sessionId = previous?.sessionId ?? null
      try {
        if (!sessionId) sessionId = await createSession()
        await postConsent(sessionId, consent)
        saveConsent({ sessionId, consent, synced: true, decidedAt: new Date().toISOString() })
        setSyncNotice(null)
      } catch {
        // Keep the choice locally and retry before the next question is sent.
        saveConsent({ sessionId, consent, synced: false, decidedAt: new Date().toISOString() })
        setSyncNotice(
          'We could not reach the DentalCare AU service just now. Your privacy choice is saved on this device and will be sent when the service is available.',
        )
      } finally {
        setConsentSaving(false)
        setConsentOpen(false)
      }
    },
    [saveConsent],
  )

  const send = useCallback(
    async (rawText: string, modality: Modality, stt?: SttMeta) => {
      const text = rawText.trim().slice(0, MAX_MESSAGE_LENGTH)
      if (!text || waitingRef.current) return
      const history = buildHistory(messagesRef.current)
      const userMessage: ChatMessage = { id: newId('u'), role: 'user', content: text, modality }
      const next = [...messagesRef.current, userMessage]
      messagesRef.current = next
      setMessages(next)
      waitingRef.current = true
      setWaiting(true)
      const seq = ++seqRef.current

      try {
        const sessionId = await ensureSession()
        const response = await postChat({ session_id: sessionId, message: text, history, modality, ...(stt ? { stt } : {}) })
        if (seq !== seqRef.current) return
        const id = newId('a')
        setMessages((prev) => [...prev, { id, role: 'assistant', response }])
        if (autoReadRef.current && ttsAvailableRef.current) {
          tts.speak(id, speechSourceText(response))
        }
      } catch (err) {
        if (seq !== seqRef.current) return
        setMessages((prev) => [
          ...prev,
          {
            id: newId('e'),
            role: 'error',
            message: errorText(err, 'Something went wrong. Please try again.'),
            retry: { text, modality, stt },
          },
        ])
      } finally {
        if (seq === seqRef.current) {
          waitingRef.current = false
          setWaiting(false)
        }
      }
    },
    [ensureSession, tts],
  )

  const retry = useCallback(
    (errorId: string) => {
      const current = messagesRef.current
      const index = current.findIndex((m) => m.id === errorId)
      const errorMessage = current[index]
      if (index < 0 || errorMessage.role !== 'error') return
      // Drop the error card and the question that failed; send() re-adds the question.
      const before = current.slice(0, index)
      const lastBefore = before[before.length - 1]
      const trimmed = lastBefore?.role === 'user' ? before.slice(0, -1) : before
      const remaining = [...trimmed, ...current.slice(index + 1)]
      messagesRef.current = remaining
      setMessages(remaining)
      void send(errorMessage.retry.text, errorMessage.retry.modality, errorMessage.retry.stt)
    },
    [send],
  )

  const handleVoiceResult = useCallback(
    (result: SttResult, modality: Modality) => {
      const text = (result.text ?? '').trim()
      if (!text) {
        setPendingStt(null)
        setNote('We didn’t catch any words. Please try again, speaking close to the microphone — or type your question.')
        return
      }
      const meta = sttToMeta({ ...result, text })
      if (typeof result.confidence === 'number' && result.confidence < LOW_CONFIDENCE) {
        setDraft(text.slice(0, MAX_MESSAGE_LENGTH))
        setPendingStt({ meta, modality })
        setNote('Please check what we heard. Correct anything that is wrong, then press Send.')
        window.setTimeout(() => textareaRef.current?.focus(), 0)
        return
      }
      setNote(null)
      void send(text, modality, meta)
    },
    [send],
  )

  const onPttResult = useCallback((result: SttResult) => handleVoiceResult(result, 'voice'), [handleVoiceResult])
  const ptt = usePushToTalk({ onResult: onPttResult })

  const handleUpload = useCallback(
    async (file: File) => {
      setUploadError(null)
      setNote(null)
      setUploading(true)
      try {
        const result = await transcribeFile(file, file.name || 'audio')
        handleVoiceResult(result, 'voice_upload')
      } catch (err) {
        const status = err instanceof ApiError ? err.status : 0
        setUploadError(
          status === 400 || status === 413 || status === 415 || status === 422
            ? 'We couldn’t understand that file. Please try a different recording (WAV, MP3, M4A, WebM or OGG).'
            : errorText(err, 'We couldn’t transcribe that file. Please try again.'),
        )
      } finally {
        setUploading(false)
      }
    },
    [handleVoiceResult],
  )

  const submitDraft = useCallback(() => {
    const pending = pendingStt
    const text = draft
    setDraft('')
    setNote(null)
    setPendingStt(null)
    void send(text, pending?.modality ?? 'text', pending?.meta)
  }, [draft, pendingStt, send])

  const changeDraft = useCallback((value: string) => {
    setDraft(value)
    if (!value.trim()) {
      setPendingStt(null)
    }
  }, [])

  const newChat = useCallback(() => {
    seqRef.current += 1
    waitingRef.current = false
    setWaiting(false)
    messagesRef.current = []
    setMessages([])
    setDraft('')
    setNote(null)
    setPendingStt(null)
    setUploadError(null)
    tts.stop()
    ptt.cancel()
    textareaRef.current?.focus()
  }, [ptt, tts])

  const openPrivacy = useCallback(() => {
    setConsentError(null)
    setConsentOpen(true)
  }, [])

  const toggleAutoRead = useCallback(
    (value: boolean) => {
      setAutoRead(value)
      if (!value) tts.stop()
    },
    [setAutoRead, tts],
  )

  const statusNotice =
    syncNotice ??
    (health?.status === 'no_index'
      ? 'The health information library has not been built yet, so answers may not be available.'
      : null)

  return (
    <div className="flex h-full flex-col">
      <a
        href="#question-input"
        className="sr-only z-50 rounded-lg bg-teal-900 px-4 py-3 font-semibold text-white focus:not-sr-only focus:absolute focus:left-3 focus:top-3"
      >
        Skip to the question box
      </a>

      <Header
        fontSize={fontSize}
        onFontSizeChange={setFontSize}
        ttsAvailable={tts.available}
        autoRead={autoRead}
        onAutoReadChange={toggleAutoRead}
        onPrivacy={openPrivacy}
        onNewChat={newChat}
        canReset={messages.length > 0 || draft.length > 0 || waiting}
      />

      <main id="main" className="min-h-0 flex-1 overflow-y-auto">
        <ChatView
          messages={messages}
          waiting={waiting}
          tts={tts}
          onRetry={retry}
          onPickStarter={(q) => void send(q, 'text')}
          statusNotice={statusNotice}
        />
      </main>

      <div className="border-t border-slate-200 bg-slate-100 dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto w-full max-w-3xl px-4 pb-1 pt-3">
          <Composer
            value={draft}
            onChange={changeDraft}
            onSubmit={submitDraft}
            waiting={waiting}
            note={note}
            onDismissNote={() => setNote(null)}
            ptt={ptt}
            uploading={uploading}
            uploadError={uploadError}
            onDismissUploadError={() => setUploadError(null)}
            onUpload={(file) => void handleUpload(file)}
            textareaRef={textareaRef}
          />
        </div>
      </div>

      <footer className="border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] dark:border-slate-800 dark:bg-slate-950">
        <div className="mx-auto w-full max-w-3xl px-4 py-2">
          <DisclaimerBanner />
        </div>
      </footer>

      <ConsentGate
        open={consentOpen}
        health={health}
        currentConsent={consentRecord ? consentRecord.consent : null}
        saving={consentSaving}
        error={consentError}
        onDecide={(consent) => void decideConsent(consent)}
        onClose={() => setConsentOpen(false)}
      />
    </div>
  )
}
