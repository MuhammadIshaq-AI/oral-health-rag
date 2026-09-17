import { ShieldAlert } from 'lucide-react'

export function DisclaimerBanner() {
  return (
    <p className="flex items-start gap-2 text-sm font-medium leading-snug text-slate-900 dark:text-slate-100">
      <ShieldAlert aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-red-700 dark:text-red-400" />
      <span>
        General information only — not a substitute for professional dental advice. In an emergency call{' '}
        <a
          href="tel:000"
          className="font-bold text-red-800 underline underline-offset-2 dark:text-red-300"
        >
          000
        </a>
        .
      </span>
    </p>
  )
}
