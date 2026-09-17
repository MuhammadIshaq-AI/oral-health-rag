import { Fragment, useMemo, type ReactNode } from 'react'
import type { Source } from '../api'
import { parseMarkdown, type Inline } from '../lib/markdown'
import { CitationChip } from './CitationChip'

interface AnswerTextProps {
  text: string
  /** Sources by citation number. When omitted, markers stay as plain text. */
  sources?: Source[]
  openCitation?: number | null
  panelId?: string
  onToggleCitation?: (n: number) => void
  className?: string
}

/** Renders markdown-ish answer text as React elements (never raw HTML). */
export function AnswerText({ text, sources, openCitation = null, panelId = '', onToggleCitation, className }: AnswerTextProps) {
  const blocks = useMemo(() => parseMarkdown(text), [text])
  const byNumber = useMemo(() => new Map((sources ?? []).map((s) => [s.n, s])), [sources])

  const renderInline = (tokens: Inline[], keyPrefix: string): ReactNode[] =>
    tokens.map((tok, i) => {
      const key = `${keyPrefix}-${i}`
      if (tok.type === 'text') return <Fragment key={key}>{tok.text}</Fragment>
      if (tok.type === 'bold') return <strong key={key}>{renderInline(tok.children, key)}</strong>
      const source = byNumber.get(tok.n)
      if (!source || !onToggleCitation) {
        return (
          <span key={key} className="text-[0.85em] text-slate-600 dark:text-slate-400">
            [{tok.n}]
          </span>
        )
      }
      return (
        <CitationChip
          key={key}
          n={tok.n}
          source={source}
          expanded={openCitation === tok.n}
          panelId={panelId}
          onToggle={onToggleCitation}
        />
      )
    })

  return (
    <div className={['space-y-3 break-words', className ?? ''].join(' ')}>
      {blocks.map((block, bi) => {
        const key = `b${bi}`
        if (block.type === 'heading') {
          return (
            <p key={key} className="font-bold">
              {renderInline(block.content, key)}
            </p>
          )
        }
        if (block.type === 'list') {
          const ListTag = block.ordered ? 'ol' : 'ul'
          return (
            <ListTag
              key={key}
              className={['space-y-1.5 pl-6', block.ordered ? 'list-decimal' : 'list-disc'].join(' ')}
            >
              {block.items.map((item, ii) => (
                <li key={`${key}-${ii}`} className="pl-1 leading-relaxed">
                  {renderInline(item, `${key}-${ii}`)}
                </li>
              ))}
            </ListTag>
          )
        }
        return (
          <p key={key} className="leading-relaxed">
            {block.lines.map((line, li) => (
              <Fragment key={`${key}-${li}`}>
                {li > 0 ? <br /> : null}
                {renderInline(line, `${key}-${li}`)}
              </Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
