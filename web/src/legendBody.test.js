import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { LegendBody } from './Legend'
import { EMPTY_FOCUS, togglePinned } from './classFocus'

const points = {
  id: 'p', kind: 'points', title: 'Tytuł', unit: 'jednostka', attribution: 'Źródło', timetable_date: '2026-11-25',
  ramp: { stops: [1], colors: ['#a', '#b'], labels: ['mało', 'dużo'] }, size_stops: [20, 50], size_label: 'odjazdy',
  has_nodata: true, nodata_label: 'brak danych X', novalue_label: 'bez wartości',
}
const html = (layer, focus = EMPTY_FOCUS) => renderToStaticMarkup(h(LegendBody, { layer, focus }))

describe('legend body (sidebar and phone overlay)', () => {
  it('has unit, class rows, size key, no-data rows and the hint, but no title, dates or sources', () => {
    const s = html(points)
    for (const t of ['jednostka', 'mało', 'dużo', 'odjazdy', '20–50', 'brak danych X', 'bez wartości', 'Wskaż klasę']) expect(s).toContain(t)
    for (const t of ['Tytuł', 'Źródło', '2026-11-25']) expect(s).not.toContain(t)
  })
  it('marks pinned rows and offers to clear them', () => {
    const s = html(points, togglePinned(EMPTY_FOCUS, 'p', 1))
    expect(s).toContain('Pokaż wszystkie klasy')
    expect(s).toContain('pinned')
    expect(s).toContain('dim')
  })
  it('draws the boundary and mask keys and a hatched row for grid layers', () => {
    expect(html({ id: 'f', kind: 'boundary' })).toContain('rdzeń miasta')
    expect(html({ id: 'm', kind: 'mask', legend: 'maska' })).toContain('maska')
    const grid = { id: 'g', kind: 'choropleth', ramp: points.ramp, has_nodata: true }
    expect(html(grid)).toContain('hatch')
  })
})
