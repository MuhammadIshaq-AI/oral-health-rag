/**
 * A deliberately tiny "markdown-ish" parser for assistant answers.
 *
 * Supports paragraphs, `- ` / `* ` / `• ` bullet lists, `1. ` numbered lists,
 * `# ` headings (rendered as bold lines), **bold**, and inline citation
 * markers such as [1], [2][3] or [1, 2]. It returns plain data tokens which
 * React components turn into elements — raw HTML is never produced, so
 * nothing in an answer can inject markup.
 */

export type Inline =
  | { type: 'text'; text: string }
  | { type: 'bold'; children: Inline[] }
  | { type: 'cite'; n: number }

export type Block =
  | { type: 'paragraph'; lines: Inline[][] }
  | { type: 'heading'; content: Inline[] }
  | { type: 'list'; ordered: boolean; items: Inline[][] }

const BULLET_RE = /^\s*(?:[-*•])\s+(.*)$/
const ORDERED_RE = /^\s*\d{1,3}[.)]\s+(.*)$/
const HEADING_RE = /^\s*#{1,6}\s+(.*)$/
// [1] or [1, 2] or [1,2,3]
const CITE_RE = /\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]/g

export function parseCitations(text: string): Inline[] {
  const out: Inline[] = []
  let last = 0
  for (const match of text.matchAll(CITE_RE)) {
    const start = match.index ?? 0
    if (start > last) out.push({ type: 'text', text: text.slice(last, start) })
    for (const part of match[1].split(',')) {
      const n = Number.parseInt(part.trim(), 10)
      if (Number.isFinite(n)) out.push({ type: 'cite', n })
    }
    last = start + match[0].length
  }
  if (last < text.length) out.push({ type: 'text', text: text.slice(last) })
  return out
}

export function parseInline(text: string): Inline[] {
  const out: Inline[] = []
  const parts = text.split('**')
  // An odd number of parts means every ** has a partner.
  const balanced = parts.length % 2 === 1
  parts.forEach((part, i) => {
    const isBold = balanced && i % 2 === 1
    if (!isBold) {
      const plain = balanced ? part : i === 0 ? part : `**${part}`
      if (plain) out.push(...parseCitations(plain))
      return
    }
    if (part.trim()) out.push({ type: 'bold', children: parseCitations(part) })
    else if (part) out.push({ type: 'text', text: part })
  })
  return mergeText(out)
}

function mergeText(tokens: Inline[]): Inline[] {
  const merged: Inline[] = []
  for (const tok of tokens) {
    const prev = merged[merged.length - 1]
    if (tok.type === 'text' && prev?.type === 'text') {
      prev.text += tok.text
    } else {
      merged.push(tok.type === 'text' ? { ...tok } : tok)
    }
  }
  return merged
}

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = []
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  let paragraph: Inline[][] | null = null
  let list: { ordered: boolean; items: Inline[][] } | null = null

  const flush = () => {
    if (paragraph && paragraph.length) blocks.push({ type: 'paragraph', lines: paragraph })
    if (list && list.items.length) blocks.push({ type: 'list', ordered: list.ordered, items: list.items })
    paragraph = null
    list = null
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      flush()
      continue
    }
    const bullet = BULLET_RE.exec(line)
    const ordered = bullet ? null : ORDERED_RE.exec(line)
    if (bullet || ordered) {
      const isOrdered = Boolean(ordered)
      if (paragraph || (list && list.ordered !== isOrdered)) flush()
      if (!list) list = { ordered: isOrdered, items: [] }
      list.items.push(parseInline((bullet ?? ordered)![1]))
      continue
    }
    const heading = HEADING_RE.exec(line)
    if (heading) {
      flush()
      blocks.push({ type: 'heading', content: parseInline(heading[1]) })
      continue
    }
    if (list) {
      // An indented continuation line belongs to the previous list item.
      if (/^\s{2,}/.test(raw) && list.items.length) {
        const item = list.items[list.items.length - 1]
        item.push({ type: 'text', text: ' ' }, ...parseInline(line.trim()))
        continue
      }
      flush()
    }
    if (!paragraph) paragraph = []
    paragraph.push(parseInline(line.trim()))
  }
  flush()
  return blocks
}

/** Plain text for speech synthesis: drops citation markers and markdown symbols. */
export function toSpeechText(source: string): string {
  return source
    .replace(CITE_RE, '')
    .replace(/\*\*/g, '')
    .replace(/^\s*#{1,6}\s+/gm, '')
    .replace(/^\s*[-*•]\s+/gm, '')
    .replace(/[ \t]+([.,;:!?])/g, '$1')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}
