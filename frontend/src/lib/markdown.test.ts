import { describe, expect, it } from 'vitest'
import { parseCitations, parseInline, parseMarkdown, toSpeechText } from './markdown'

describe('parseCitations', () => {
  it('splits text around citation markers', () => {
    expect(parseCitations('Brush twice a day [1] and floss [2][3].')).toEqual([
      { type: 'text', text: 'Brush twice a day ' },
      { type: 'cite', n: 1 },
      { type: 'text', text: ' and floss ' },
      { type: 'cite', n: 2 },
      { type: 'cite', n: 3 },
      { type: 'text', text: '.' },
    ])
  })

  it('expands comma separated markers', () => {
    expect(parseCitations('[1, 2]')).toEqual([
      { type: 'cite', n: 1 },
      { type: 'cite', n: 2 },
    ])
  })

  it('ignores non-numeric brackets', () => {
    expect(parseCitations('see [note]')).toEqual([{ type: 'text', text: 'see [note]' }])
  })
})

describe('parseInline', () => {
  it('parses bold containing citations', () => {
    expect(parseInline('**Call 000 [2]** now')).toEqual([
      { type: 'bold', children: [{ type: 'text', text: 'Call 000 ' }, { type: 'cite', n: 2 }] },
      { type: 'text', text: ' now' },
    ])
  })

  it('leaves unbalanced asterisks as text', () => {
    expect(parseInline('a ** b')).toEqual([{ type: 'text', text: 'a ** b' }])
  })

  it('does not interpret HTML', () => {
    expect(parseInline('<img src=x onerror=alert(1)>')).toEqual([
      { type: 'text', text: '<img src=x onerror=alert(1)>' },
    ])
  })
})

describe('parseMarkdown', () => {
  it('builds paragraphs and lists', () => {
    const blocks = parseMarkdown('Intro line [1]\n\n- first\n* second [2]\n\nOutro')
    expect(blocks.map((b) => b.type)).toEqual(['paragraph', 'list', 'paragraph'])
    const list = blocks[1]
    expect(list.type === 'list' && list.items.length).toBe(2)
  })

  it('separates a list directly following a paragraph', () => {
    const blocks = parseMarkdown('You can:\n- rinse\n- rest')
    expect(blocks.map((b) => b.type)).toEqual(['paragraph', 'list'])
  })

  it('supports ordered lists and headings', () => {
    const blocks = parseMarkdown('# Steps\n1. One\n2. Two')
    expect(blocks[0].type).toBe('heading')
    expect(blocks[1]).toMatchObject({ type: 'list', ordered: true })
  })
})

describe('toSpeechText', () => {
  it('strips markers and markdown', () => {
    expect(toSpeechText('**Rinse** gently [1].\n- Use salt water [2]')).toBe('Rinse gently.\nUse salt water')
  })
})
