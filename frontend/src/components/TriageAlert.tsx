import { AlertTriangle, HeartHandshake, Info, MessageSquare, Phone, Siren } from 'lucide-react'
import type { Triage } from '../api'
import { safeActionHref } from '../lib/sources'
import { AnswerText } from './AnswerText'

interface TriageAlertProps {
  triage: Triage
}

const STYLES = {
  emergency: {
    box: 'border-red-800 bg-red-700 text-white dark:border-red-400 dark:bg-red-800',
    button: 'bg-white text-red-800 hover:bg-red-50 dark:bg-white dark:text-red-900',
    secondary: 'border-2 border-white text-white hover:bg-red-800 dark:hover:bg-red-900',
  },
  crisis: {
    box: 'border-indigo-950 bg-indigo-900 text-white dark:border-indigo-300 dark:bg-indigo-950',
    button: 'bg-white text-indigo-900 hover:bg-indigo-50',
    secondary: 'border-2 border-white text-white hover:bg-indigo-950 dark:hover:bg-indigo-900',
  },
  urgent: {
    box: 'border-amber-600 bg-amber-50 text-amber-950 dark:border-amber-400 dark:bg-amber-950 dark:text-amber-50',
    button: 'bg-amber-800 text-white hover:bg-amber-900 dark:bg-amber-300 dark:text-amber-950 dark:hover:bg-amber-200',
    secondary:
      'border-2 border-amber-800 text-amber-950 hover:bg-amber-100 dark:border-amber-300 dark:text-amber-50 dark:hover:bg-amber-900',
  },
  info: {
    box: 'border-sky-600 bg-sky-50 text-sky-950 dark:border-sky-400 dark:bg-sky-950 dark:text-sky-50',
    button: 'bg-sky-800 text-white hover:bg-sky-900 dark:bg-sky-300 dark:text-sky-950',
    secondary: 'border-2 border-sky-800 text-sky-950 hover:bg-sky-100 dark:border-sky-300 dark:text-sky-50 dark:hover:bg-sky-900',
  },
} as const

function ActionIcon({ href }: { href: string }) {
  if (href.startsWith('sms:')) return <MessageSquare aria-hidden="true" className="h-6 w-6 shrink-0" />
  if (href.startsWith('tel:')) return <Phone aria-hidden="true" className="h-6 w-6 shrink-0" />
  return null
}

/** Safety alert shown at the top of an assistant message. */
export function TriageAlert({ triage }: TriageAlertProps) {
  const severity = triage.severity
  if (severity === 'none') return null
  if (!triage.title && !triage.message && triage.actions.length === 0) return null

  const style = STYLES[severity]
  const prominent = severity === 'emergency' || severity === 'crisis'
  const Icon =
    severity === 'emergency' ? Siren : severity === 'crisis' ? HeartHandshake : severity === 'urgent' ? AlertTriangle : Info

  return (
    <div
      role={prominent ? 'alert' : undefined}
      className={['rounded-2xl border-2 p-4 sm:p-5', style.box].join(' ')}
    >
      <div className="flex items-start gap-3">
        <Icon aria-hidden="true" className={prominent ? 'mt-0.5 h-8 w-8 shrink-0' : 'mt-0.5 h-6 w-6 shrink-0'} />
        <div className="min-w-0 flex-1">
          {triage.title ? (
            <h3 className={prominent ? 'text-xl font-bold leading-snug' : 'text-lg font-bold leading-snug'}>
              {triage.title}
            </h3>
          ) : null}
          {triage.message ? <AnswerText text={triage.message} className={triage.title ? 'mt-2' : ''} /> : null}
        </div>
      </div>

      {triage.actions.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {triage.actions.map((action, i) => {
            const href = safeActionHref(action.href)
            if (!href) return null
            const primary = action.kind === 'emergency' || action.kind === 'crisis' || i === 0
            const external = href.startsWith('http')
            return (
              <li key={`${action.href}-${i}`}>
                <a
                  href={href}
                  {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                  className={[
                    'flex min-h-14 w-full items-center justify-center gap-3 rounded-xl px-4 py-3 text-center text-lg font-bold no-underline shadow-sm',
                    prominent ? 'focus-visible:outline-offset-4 focus-visible:outline-white' : 'focus-visible:outline-offset-4',
                    primary ? style.button : style.secondary,
                  ].join(' ')}
                >
                  <ActionIcon href={href} />
                  <span>{action.label}</span>
                </a>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
