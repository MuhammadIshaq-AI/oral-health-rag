export type FontSize = 'standard' | 'large' | 'xlarge'

const OPTIONS: { value: FontSize; short: string; label: string; sample: string }[] = [
  { value: 'standard', short: 'A', label: 'Standard text size', sample: 'text-base' },
  { value: 'large', short: 'A', label: 'Large text size', sample: 'text-xl' },
  { value: 'xlarge', short: 'A', label: 'Extra large text size', sample: 'text-2xl' },
]

interface FontSizeControlProps {
  value: FontSize
  onChange: (value: FontSize) => void
}

export function FontSizeControl({ value, onChange }: FontSizeControlProps) {
  return (
    <div role="group" aria-label="Text size" className="flex items-center gap-2">
      <span aria-hidden="true" className="hidden text-sm font-medium text-slate-700 sm:inline dark:text-slate-300">
        Text size
      </span>
      <div className="inline-flex overflow-hidden rounded-xl border-2 border-slate-300 dark:border-slate-600">
        {OPTIONS.map((opt, i) => {
          const selected = opt.value === value
          return (
            <button
              key={opt.value}
              type="button"
              aria-pressed={selected}
              aria-label={opt.label}
              title={opt.label}
              onClick={() => onChange(opt.value)}
              className={[
                'inline-flex h-12 min-w-12 items-center justify-center px-2 font-bold leading-none',
                i > 0 ? 'border-l-2 border-slate-300 dark:border-slate-600' : '',
                selected
                  ? 'bg-teal-800 text-white dark:bg-teal-300 dark:text-slate-950'
                  : 'bg-white text-slate-900 hover:bg-slate-100 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800',
              ].join(' ')}
            >
              <span aria-hidden="true" className={opt.sample}>
                {opt.short}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
