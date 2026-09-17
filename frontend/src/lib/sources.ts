import type { Source } from '../api'

const JURISDICTIONS: Record<string, string> = {
  AU: 'Australia',
  NSW: 'NSW',
  VIC: 'Victoria',
  QLD: 'Queensland',
  SA: 'South Australia',
  WA: 'Western Australia',
  TAS: 'Tasmania',
  NT: 'Northern Territory',
  ACT: 'ACT',
}

export function jurisdictionLabel(source: Pick<Source, 'jurisdiction' | 'secondary' | 'source_org'>): string {
  const code = (source.jurisdiction || '').toUpperCase()
  if (source.secondary || code === 'INT') {
    const org = /world health|\bwho\b/i.test(source.source_org) ? 'WHO' : source.source_org
    return `International${org ? ` (${org})` : ''} — not Australian guidance`
  }
  return JURISDICTIONS[code] ?? (code || 'Australia')
}

export function formatRetrievedDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric' })
}

/** Only allow web links for source pages. */
export function safeHttpUrl(url: string): string | null {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.toString() : null
  } catch {
    return null
  }
}

/** Allow phone, SMS, e-mail and web links for triage actions. */
export function safeActionHref(href: string): string | null {
  const trimmed = href.trim()
  if (/^(tel|sms):[+\d\s()-]+$/i.test(trimmed)) return trimmed.replace(/\s+/g, '')
  if (/^mailto:/i.test(trimmed)) return trimmed
  return safeHttpUrl(trimmed)
}
