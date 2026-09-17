import { describe, expect, it } from 'vitest'

describe('App renders', () => {
  it('produces markup without throwing', async () => {
    const store = new Map<string, string>()
    const win = {
      localStorage: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => void store.set(k, v),
        removeItem: (k: string) => void store.delete(k),
      },
      matchMedia: () => ({ matches: false }),
      innerHeight: 800,
      devicePixelRatio: 1,
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
    }
    ;(globalThis as unknown as { window: unknown }).window = win

    const [{ renderToStaticMarkup }, { default: App }] = await Promise.all([
      import('react-dom/server'),
      import('./App'),
    ])
    const html = renderToStaticMarkup(<App />)
    expect(html).toContain('DentalCare AU')
    expect(html).toContain('In an emergency call')
    expect(html).toContain('Why do my gums bleed when I brush?')
    expect(html).toContain('I agree — log my conversation for research')
  })
})
