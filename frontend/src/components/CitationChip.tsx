import { ExternalLink, Globe2, MapPin, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { Source } from '../api'
import { formatRetrievedDate, jurisdictionLabel, safeHttpUrl } from '../lib/sources'

interface CitationChipProps {
  n: number
  source: Source
  expanded: boolean
  panelId: string
  onToggle: (n: number) => void
}

/** Inline [n] marker rendered as a button that opens the passage panel below the answer. */
export function CitationChip({ n, source, expanded, panelId, onToggle }: CitationChipProps) {
  return (
    <button
      type="button"
      onClick={() => onToggle(n)}
      aria-expanded={expanded}
      aria-controls={panelId}
      data-citation={n}
      aria-label={`Source ${n}: ${source.source_org}. ${expanded ? 'Hide' : 'Show'} details`}
      className={[
        'mx-0.5 inline-flex min-h-8 min-w-8 items-center justify-center rounded-full border px-2 align-middle',
        'text-[0.8em] font-semibold leading-none transition-colors',
        expanded
          ? 'border-teal-800 bg-teal-800 text-white dark:border-teal-300 dark:bg-teal-300 dark:text-slate-950'
          : 'border-teal-700 bg-teal-50 text-teal-900 hover:bg-teal-100 dark:border-teal-400 dark:bg-teal-950 dark:text-teal-100 dark:hover:bg-teal-900',
      ].join(' ')}
    >
      {n}
    </button>
  )
}

interface CitationPanelProps {
  source: Source
  id: string
  onClose: () => void
}

export function CitationPanel({ source, id, onClose }: CitationPanelProps) {
  const sectionRef = useRef<HTMLElement>(null)
  const href = safeHttpUrl(source.url)
  const label = jurisdictionLabel(source)
  const international = source.secondary || source.jurisdiction.toUpperCase() === 'INT'

  useEffect(() => {
    // Keep focus on the chip (disclosure pattern) but make sure the panel is visible.
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    sectionRef.current?.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' })
  }, [source.n])

  return (
    <section
      id={id}
      ref={sectionRef}
      aria-labelledby={`${id}-title`}
      className="mt-3 rounded-xl border-2 border-teal-700 bg-white p-4 text-slate-900 dark:border-teal-400 dark:bg-slate-900 dark:text-slate-100"
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-0.5 inline-flex h-8 min-w-8 shrink-0 items-center justify-center rounded-full bg-teal-800 px-2 text-sm font-bold text-white dark:bg-teal-300 dark:text-slate-950"
        >
          {source.n}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-700 dark:text-slate-300">
            {source.source_org}
          </p>
          <h3
            id={`${id}-title`}
            className="text-base font-bold leading-snug"
          >
            <span className="sr-only">Source {source.n}: </span>
            {source.page_title}
            {source.section ? <span className="font-normal"> — {source.section}</span> : null}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close source details"
          className="-mr-2 -mt-2 inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          <X aria-hidden="true" className="h-6 w-6" />
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span
          className={[
            'inline-flex items-center gap-1 rounded-full px-3 py-1 font-semibold',
            international
              ? 'bg-amber-100 text-amber-950 dark:bg-amber-900 dark:text-amber-50'
              : 'bg-teal-100 text-teal-950 dark:bg-teal-900 dark:text-teal-50',
          ].join(' ')}
        >
          {international ? (
            <Globe2 aria-hidden="true" className="h-4 w-4" />
          ) : (
            <MapPin aria-hidden="true" className="h-4 w-4" />
          )}
          {label}
        </span>
        <span className="text-slate-700 dark:text-slate-300">Retrieved {formatRetrievedDate(source.retrieved_at)}</span>
      </div>

      <blockquote
        tabIndex={0}
        aria-label="Exact passage from the source"
        className="mt-3 max-h-60 overflow-y-auto whitespace-pre-line rounded-lg border-l-4 border-teal-700 bg-slate-50 p-3 text-base leading-relaxed text-slate-900 dark:border-teal-400 dark:bg-slate-800 dark:text-slate-100"
      >
        {source.text}
      </blockquote>

      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex min-h-12 items-center gap-2 rounded-lg px-1 font-semibold text-teal-800 underline underline-offset-4 hover:text-teal-950 dark:text-teal-300 dark:hover:text-teal-100"
        >
          Open source page
          <ExternalLink aria-hidden="true" className="h-5 w-5" />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      ) : null}
    </section>
  )
}
