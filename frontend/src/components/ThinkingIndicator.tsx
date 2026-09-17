export function ThinkingIndicator() {
  return (
    <div role="status" aria-live="polite" className="flex justify-start">
      <div className="surface-card flex items-center gap-3 rounded-bl-md px-4 py-3 text-slate-800 dark:text-slate-200">
        <span aria-hidden="true" className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-teal-700 motion-safe:animate-bounce dark:bg-teal-300 [animation-delay:-0.3s]" />
          <span className="h-2.5 w-2.5 rounded-full bg-teal-700 motion-safe:animate-bounce dark:bg-teal-300 [animation-delay:-0.15s]" />
          <span className="h-2.5 w-2.5 rounded-full bg-teal-700 motion-safe:animate-bounce dark:bg-teal-300" />
        </span>
        <span>Looking through Australian health sources…</span>
      </div>
    </div>
  )
}
