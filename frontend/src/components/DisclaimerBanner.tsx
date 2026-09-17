/**
 * The single always-visible caveat under the composer. Per-answer safety text
 * (the "general information, not dental advice" line and any emergency banner)
 * comes from the backend with each response; technical details about the model,
 * corpus and provider live in the Privacy dialog.
 */
export function DisclaimerBanner() {
  return (
    <p className="text-center text-sm leading-snug text-slate-600 dark:text-slate-400">
      DentalCare AU is an AI assistant and can make mistakes — check the sources shown with each
      answer.
    </p>
  )
}
