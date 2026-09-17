import { BookOpen } from 'lucide-react'
import type { Source } from '../api'

interface SourceListProps {
  sources: Source[]
  openCitation: number | null
  panelId: string
  onToggle: (n: number) => void
}

/** Compact list of the sources an answer actually cites. */
export function SourceList({ sources, openCitation, panelId, onToggle }: SourceListProps) {
  const cited = sources.filter((s) => s.cited).sort((a, b) => a.n - b.n)
  if (cited.length === 0) return null

  return (
    <div className="mt-4 border-t border-slate-200 pt-3 dark:border-slate-700">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
        <BookOpen aria-hidden="true" className="h-4 w-4" />
        Sources
      </h3>
      <ul className="mt-2 flex flex-wrap gap-2">
        {cited.map((s) => {
          const expanded = openCitation === s.n
          return (
            <li key={s.n}>
              <button
                type="button"
                onClick={() => onToggle(s.n)}
                aria-expanded={expanded}
                aria-controls={panelId}
                data-citation={s.n}
                className={[
                  'inline-flex min-h-12 max-w-full items-center gap-2 rounded-full border py-1 pl-1 pr-4 text-left text-sm font-medium',
                  expanded
                    ? 'border-teal-800 bg-teal-800 text-white dark:border-teal-300 dark:bg-teal-300 dark:text-slate-950'
                    : 'border-slate-300 bg-white text-slate-900 hover:border-teal-700 hover:bg-teal-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800',
                ].join(' ')}
              >
                <span
                  aria-hidden="true"
                  className={[
                    'inline-flex h-9 min-w-9 items-center justify-center rounded-full px-2 font-bold',
                    expanded
                      ? 'bg-white text-teal-900 dark:bg-slate-950 dark:text-teal-200'
                      : 'bg-teal-100 text-teal-900 dark:bg-teal-900 dark:text-teal-50',
                  ].join(' ')}
                >
                  {s.n}
                </span>
                <span className="line-clamp-2">
                  <span className="sr-only">Source {s.n}: </span>
                  {s.source_org}
                  {s.secondary ? <span className="sr-only"> (international, not Australian guidance)</span> : null}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
