import { MessageCircleQuestion } from 'lucide-react'

const STARTER_QUESTIONS = [
  'Why do my gums bleed when I brush?',
  'Is my child eligible for the Child Dental Benefits Schedule?',
  'How do I look after my dentures?',
  'What can help with a dry mouth?',
  'Do wisdom teeth always need to come out?',
  'How can I get cheaper dental care?',
] as const

interface StarterQuestionsProps {
  onPick: (question: string) => void
  disabled?: boolean
}

export function StarterQuestions({ onPick, disabled }: StarterQuestionsProps) {
  return (
    <section aria-labelledby="starter-heading" className="py-4">
      <h2 id="starter-heading" className="text-2xl font-bold text-slate-900 dark:text-slate-50">
        Ask a question about your teeth or mouth
      </h2>
      <p className="mt-2 text-slate-700 dark:text-slate-300">
        Type or speak your question. Answers come from Australian health organisations, with links to each source.
      </p>
      <p className="mt-4 font-semibold text-slate-800 dark:text-slate-200">Or try one of these:</p>
      <ul className="mt-3 grid gap-3 sm:grid-cols-2">
        {STARTER_QUESTIONS.map((q) => (
          <li key={q}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onPick(q)}
              className="flex min-h-14 w-full items-center gap-3 rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-left font-medium text-slate-900 shadow-sm hover:border-teal-700 hover:bg-teal-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-teal-400 dark:hover:bg-slate-800"
            >
              <MessageCircleQuestion aria-hidden="true" className="h-6 w-6 shrink-0 text-teal-700 dark:text-teal-300" />
              <span>{q}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
