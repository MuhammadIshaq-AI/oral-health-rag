import { RefreshCw, WifiOff } from 'lucide-react'

interface ErrorCardProps {
  message: string
  onRetry?: () => void
  disabled?: boolean
}

export function ErrorCard({ message, onRetry, disabled }: ErrorCardProps) {
  return (
    <div
      role="alert"
      className="rounded-2xl border-2 border-rose-300 bg-rose-50 p-4 text-rose-950 dark:border-rose-500 dark:bg-rose-950 dark:text-rose-50"
    >
      <div className="flex items-start gap-3">
        <WifiOff aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">We couldn&rsquo;t get an answer</p>
          <p className="mt-1">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          disabled={disabled}
          className="mt-3 inline-flex min-h-12 items-center gap-2 rounded-xl bg-rose-800 px-5 font-semibold text-white hover:bg-rose-900 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-rose-200 dark:text-rose-950 dark:hover:bg-rose-100"
        >
          <RefreshCw aria-hidden="true" className="h-5 w-5" />
          Try again
        </button>
      ) : null}
    </div>
  )
}
