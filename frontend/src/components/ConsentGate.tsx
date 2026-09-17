import { Check, Cloud, Loader2, Lock, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { Health } from '../api'

interface ConsentGateProps {
  open: boolean
  health: Health | null
  /** null when the user has not chosen yet (first visit). */
  currentConsent: boolean | null
  saving: boolean
  error: string | null
  onDecide: (consent: boolean) => void
  onClose: () => void
}

/**
 * Plain-English research consent and privacy information, shown before first
 * use and re-openable from the header "Privacy" button.
 */
export function ConsentGate({ open, health, currentConsent, saving, error, onDecide, onClose }: ConsentGateProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const firstVisit = currentConsent === null

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal()
      else dialog.setAttribute('open', '')
      headingRef.current?.focus()
    } else if (!open && dialog.open) {
      if (typeof dialog.close === 'function') dialog.close()
      else dialog.removeAttribute('open')
    }
  }, [open])

  const external = health !== null && health.local_only === false

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="consent-title"
      aria-describedby="consent-intro"
      onCancel={(e) => {
        // Escape closes only when a choice already exists.
        e.preventDefault()
        if (!firstVisit && !saving) onClose()
      }}
      className="m-auto max-h-[100dvh] w-full max-w-2xl overflow-y-auto rounded-none bg-white p-0 text-slate-900 shadow-2xl backdrop:bg-slate-900/70 sm:max-h-[92dvh] sm:rounded-2xl dark:bg-slate-900 dark:text-slate-100"
    >
      <div className="p-5 sm:p-7">
        <div className="flex items-start justify-between gap-3">
          <h2
            id="consent-title"
            ref={headingRef}
            tabIndex={-1}
            className="text-2xl font-bold leading-tight text-teal-900 focus:outline-none dark:text-teal-200"
          >
            {firstVisit ? 'Welcome to DentalCare AU' : 'Privacy and research'}
          </h2>
          {!firstVisit ? (
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              aria-label="Close privacy information"
              className="-mr-2 -mt-1 inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X aria-hidden="true" className="h-7 w-7" />
            </button>
          ) : null}
        </div>

        <div id="consent-intro" className="mt-4 space-y-4 leading-relaxed">
          <p>
            DentalCare AU is a <strong>research tool</strong>. It answers general questions about teeth and mouth
            health using information from Australian health organisations, and shows you where each answer came from.
          </p>

          <div className="rounded-xl border-2 border-red-700 bg-red-50 p-4 text-red-950 dark:border-red-400 dark:bg-red-950 dark:text-red-50">
            <p className="font-semibold">General information only — not a substitute for professional dental advice.</p>
            <p className="mt-1">
              It cannot examine you or diagnose a problem. In an emergency call <strong>000</strong>. For a dental
              problem, please see a dentist or doctor.
            </p>
          </div>

          <h3 className="text-lg font-bold">What we keep</h3>
          <ul className="list-disc space-y-2 pl-6">
            <li>
              If you agree, your questions and the answers are <strong>logged anonymously</strong> for research on how
              well this tool works.
            </li>
            <li>
              We use a <strong>random session number</strong>. We never ask for your name, email or an account.
            </li>
            <li>
              When you speak, your <strong>audio is turned into text on this computer and is not stored</strong>.
            </li>
            <li>Please don&rsquo;t type personal details such as your name, address or Medicare number.</li>
            <li>You can change your choice at any time with the &ldquo;Privacy&rdquo; button at the top.</li>
          </ul>

          {external ? (
            <div className="flex items-start gap-3 rounded-xl border-2 border-amber-600 bg-amber-50 p-4 text-amber-950 dark:border-amber-400 dark:bg-amber-950 dark:text-amber-50">
              <Cloud aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0" />
              <p>
                <strong>Please note:</strong> to write answers, your questions (as text) are sent to an external AI
                service{health?.provider ? ` (${health.provider})` : ''}. Your audio is not sent.
              </p>
            </div>
          ) : health?.local_only ? (
            <div className="flex items-start gap-3 rounded-xl bg-teal-50 p-4 text-teal-950 dark:bg-teal-950 dark:text-teal-50">
              <Lock aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0" />
              <p>Answers are written by an AI model running locally. Your questions are not sent to an outside AI service.</p>
            </div>
          ) : null}

          {!firstVisit ? (
            <p className="font-medium">
              Your current choice:{' '}
              <strong>{currentConsent ? 'research logging is on' : 'research logging is off'}</strong>.
            </p>
          ) : null}
        </div>

        {error ? (
          <p role="alert" className="mt-4 rounded-xl bg-rose-50 p-3 text-rose-950 dark:bg-rose-950 dark:text-rose-50">
            {error}
          </p>
        ) : null}

        <div className="mt-6 grid gap-3">
          <button
            type="button"
            onClick={() => onDecide(true)}
            disabled={saving}
            aria-pressed={currentConsent === true}
            className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl bg-teal-800 px-5 py-3 text-center text-lg font-bold text-white hover:bg-teal-900 disabled:opacity-60 dark:bg-teal-300 dark:text-slate-950 dark:hover:bg-teal-200"
          >
            {saving ? <Loader2 aria-hidden="true" className="h-5 w-5 motion-safe:animate-spin" /> : null}
            {currentConsent === true ? <Check aria-hidden="true" className="h-6 w-6" /> : null}
            I agree — log my conversation for research
          </button>
          <button
            type="button"
            onClick={() => onDecide(false)}
            disabled={saving}
            aria-pressed={currentConsent === false}
            className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl border-2 border-teal-800 bg-white px-5 py-3 text-center text-lg font-bold text-teal-900 hover:bg-teal-50 disabled:opacity-60 dark:border-teal-300 dark:bg-slate-900 dark:text-teal-100 dark:hover:bg-slate-800"
          >
            {currentConsent === false ? <Check aria-hidden="true" className="h-6 w-6" /> : null}
            Use without research logging
          </button>
        </div>
      </div>
    </dialog>
  )
}
