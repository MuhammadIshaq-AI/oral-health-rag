import { RotateCcw, ShieldCheck, Volume2, VolumeX } from 'lucide-react'
import { FontSizeControl, type FontSize } from './FontSizeControl'

interface HeaderProps {
  fontSize: FontSize
  onFontSizeChange: (size: FontSize) => void
  ttsAvailable: boolean
  autoRead: boolean
  onAutoReadChange: (value: boolean) => void
  onPrivacy: () => void
  onNewChat: () => void
  canReset: boolean
}

export function Header({
  fontSize,
  onFontSizeChange,
  ttsAvailable,
  autoRead,
  onAutoReadChange,
  onPrivacy,
  onNewChat,
  canReset,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto w-full max-w-3xl px-4 py-2">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="flex items-center gap-2 text-xl font-bold leading-tight text-teal-900 dark:text-teal-200">
              <ToothMark />
              DentalCare AU
            </h1>
            <p className="text-sm leading-snug text-slate-700 dark:text-slate-300">
              Oral health information from Australian health sources
            </p>
          </div>
          <button
            type="button"
            onClick={onNewChat}
            disabled={!canReset}
            className="inline-flex min-h-12 shrink-0 items-center gap-2 rounded-xl border-2 border-teal-800 px-3 font-semibold text-teal-900 hover:bg-teal-50 disabled:cursor-not-allowed disabled:border-slate-300 disabled:text-slate-500 dark:border-teal-300 dark:text-teal-100 dark:hover:bg-slate-800 dark:disabled:border-slate-700 dark:disabled:text-slate-500"
          >
            <RotateCcw aria-hidden="true" className="h-5 w-5" />
            New chat
          </button>
        </div>

        <div role="group" aria-label="Display and privacy settings" className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
          <FontSizeControl value={fontSize} onChange={onFontSizeChange} />
          {ttsAvailable ? (
            <button
              type="button"
              role="switch"
              aria-checked={autoRead}
              onClick={() => onAutoReadChange(!autoRead)}
              className="inline-flex min-h-12 items-center gap-2 rounded-xl px-2 font-medium text-slate-900 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-800"
            >
              {autoRead ? (
                <Volume2 aria-hidden="true" className="h-5 w-5 text-teal-800 dark:text-teal-300" />
              ) : (
                <VolumeX aria-hidden="true" className="h-5 w-5 text-slate-600 dark:text-slate-400" />
              )}
              <span>Read answers aloud</span>
              <span
                aria-hidden="true"
                className={[
                  'relative inline-block h-7 w-12 rounded-full border-2 transition-colors',
                  autoRead
                    ? 'border-teal-800 bg-teal-800 dark:border-teal-300 dark:bg-teal-300'
                    : 'border-slate-500 bg-slate-200 dark:border-slate-400 dark:bg-slate-700',
                ].join(' ')}
              >
                <span
                  className={[
                    'absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform',
                    autoRead ? 'translate-x-5 dark:bg-slate-950' : 'translate-x-0 dark:bg-slate-200',
                  ].join(' ')}
                />
              </span>
            </button>
          ) : null}
          <button
            type="button"
            onClick={onPrivacy}
            className="inline-flex min-h-12 items-center gap-2 rounded-xl px-2 font-medium text-slate-900 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-800"
          >
            <ShieldCheck aria-hidden="true" className="h-5 w-5 text-teal-800 dark:text-teal-300" />
            Privacy
          </button>
        </div>
      </div>
    </header>
  )
}

function ToothMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 64 64" className="h-7 w-7 shrink-0">
      <rect width="64" height="64" rx="14" className="fill-teal-800 dark:fill-teal-300" />
      <path
        d="M20 14c-6 0-10 5-10 11 0 7 4 10 5 17 1 6 3 10 6 10s4-4 5-9c1-4 2-6 6-6s5 2 6 6c1 5 2 9 5 9s5-4 6-10c1-7 5-10 5-17 0-6-4-11-10-11-5 0-8 3-12 3s-7-3-12-3z"
        className="fill-white dark:fill-slate-950"
      />
    </svg>
  )
}
