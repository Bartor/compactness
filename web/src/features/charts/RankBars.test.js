import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import RankBars, { rankRows } from './RankBars'

const rows = [
  { key: 'a', label: 'Aaa', value: 10 }, { key: 'b', label: 'Bbb', value: 30 },
  { key: 'c', label: 'Ccc', value: null }, { key: 'd', label: 'Ddd', value: 20 },
]
const html = (p) => renderToStaticMarkup(h(RankBars, { rows, label: 'Miara', ...p }))

describe('RankBars', () => {
  it('sorts best first by the direction, with rows without a value last and never as a bar', () => {
    expect(rankRows(rows, 'high').map((r) => r.key)).toEqual(['b', 'd', 'a', 'c'])
    expect(rankRows(rows, 'low').map((r) => r.key)).toEqual(['a', 'd', 'b', 'c'])
    expect(rankRows(rows, null).map((r) => r.key)).toEqual(['b', 'd', 'a', 'c'])
  })
  it('writes the value at every bar, the median, and "brak danych" for a missing value', () => {
    const s = html({ median: 20, format: (v) => (v == null ? 'brak danych' : `${v} jedn.`) })
    for (const t of ['10 jedn.', '30 jedn.', '20 jedn.', 'mediana 20 jedn.', 'brak danych']) expect(s).toContain(t)
    expect(s.indexOf('Bbb')).toBeLessThan(s.indexOf('Aaa'))
    expect((s.match(/<rect[^>]*rx="3"/g) || []).length).toBe(3)   // three bars, none for the missing city
  })
  it('starts bars at zero and has the table switch and the linking', () => {
    const s = html({ selected: 'a', hot: 'b', pinned: ['d'] })
    expect(s).toContain('aria-pressed="false"')
    expect(s).toContain('chx-label sel')
    expect(s).toContain('chx-rowbg on')
    expect(s).toContain('Słupki zaczynają się od zera')
  })
  it('copes with no rows and with all-equal or negative values', () => {
    expect(() => html({ rows: [] })).not.toThrow()
    expect(() => html({ rows: [{ key: 'a', label: 'A', value: 5 }, { key: 'b', label: 'B', value: 5 }] })).not.toThrow()
    expect(() => html({ rows: [{ key: 'a', label: 'A', value: -5 }, { key: 'b', label: 'B', value: 2 }] })).not.toThrow()
  })
});
