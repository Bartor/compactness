import { describe, expect, it } from 'vitest'
import {
  NODATA_GREY, ZOOM_BANDS, bandFilter, drawnAt, focusPaint, pointLayerIds, pointSpecs, radiusExpression, sizeClasses,
} from './pointLayers'
import { layerSpecs, sourceSpec } from './mapLayers'
import { NO_DATA, SUM_LABEL, modesText, nodePopupModel, num, pct, renderNodePopup, transferSumText } from './nodePopup'
import { classIndex } from './ramp'

const layer = {
  id: 'transfer_walk', kind: 'points', type: 'geojson', url: 'data/transfer_nodes.geojson', property: 'walk_dir',
  ramp: { stops: [1, 2, 3, 5], colors: ['#c0', '#c1', '#c2', '#c3', '#c4'] },
  size_property: 'dep_h', size_stops: [20, 50, 100, 200], timetable_date: '2026-11-25',
}
const flat = (s) => s.replace(/ /g, ' ')

describe('points layer specs', () => {
  it('draws rings under coloured circles, quiet bands under busy ones, each band from its zoom', () => {
    const s = pointSpecs(layer)
    expect(s.map((x) => x.id)).toEqual([
      ...[3, 2, 1, 0].map((k) => `transfer_walk:nodata:${k}`),
      ...[3, 2, 1, 0].map((k) => `transfer_walk:pts:${k}`),
    ])
    expect(s.every((x) => x.type === 'circle')).toBe(true)
    expect(s.filter((x) => x.id.includes(':pts:')).map((x) => x.minzoom)).toEqual([13, 11.5, 10, 8])
    expect(pointLayerIds(layer)).toHaveLength(8)
    expect(layerSpecs(layer)).toEqual(s)
    expect(sourceSpec(layer).type).toBe('geojson')
  })
  it('colours by a step over the ramp and guards missing values', () => {
    const c = pointSpecs(layer).find((x) => x.id === 'transfer_walk:pts:0')
    expect(c.paint['circle-color'][2]).toEqual(['step', ['get', 'walk_dir'], '#c0', 1, '#c1', 2, '#c2', 3, '#c3', 5, '#c4'])
    expect(c.paint['circle-stroke-color']).toBe('#FFFFFF')
    expect(c.filter[2]).toEqual(['==', ['typeof', ['get', 'walk_dir']], 'number'])
  })
  it('no data is a hollow grey ring: transparent fill, grey stroke, filter on a missing number', () => {
    const r = pointSpecs(layer).find((x) => x.id === 'transfer_walk:nodata:2')
    expect(r.paint['circle-color']).toBe('rgba(0,0,0,0)')
    expect(r.paint['circle-stroke-color']).toBe(NODATA_GREY)
    expect(r.filter[2]).toEqual(['!', ['==', ['typeof', ['get', 'walk_dir']], 'number']])
  })
  it('zoom bands: 100+ from z8, 50+ from z10, 20+ from z11.5, everything from z13', () => {
    expect(ZOOM_BANDS.map((b) => [b.minzoom, b.min])).toEqual([[8, 100], [10, 50], [11.5, 20], [13, null]])
    expect(drawnAt(150, 8)).toBe(true)
    expect(drawnAt(99, 8)).toBe(false)
    expect(drawnAt(99, 10)).toBe(true)
    expect(drawnAt(49, 10)).toBe(false)
    expect(drawnAt(49, 11.5)).toBe(true)
    expect(drawnAt(19, 11.5)).toBe(false)
    expect(drawnAt(0.7, 13)).toBe(true)
    expect(drawnAt(300, 7.9)).toBe(false)
    // each node falls into exactly one band
    for (const d of [0, 5, 19.9, 20, 49.9, 50, 99.9, 100, 500]) {
      expect(ZOOM_BANDS.filter((b) => (b.min == null || d >= b.min) && (b.max == null || d < b.max))).toHaveLength(1)
    }
    expect(bandFilter(layer, ZOOM_BANDS[3])).toEqual(['all', ['<', ['to-number', ['get', 'dep_h'], 0], 20]])
  })
  it('radius grows with departures, from about 3 px to about 11 px, and mildly with zoom', () => {
    const e = radiusExpression(layer)
    expect(e.slice(0, 4)).toEqual(['interpolate', ['linear'], ['zoom'], 8])
    const lo = e[4]
    const hi = e[6]
    expect(lo[0]).toBe('step')
    expect(lo[2]).toBeCloseTo(3 * 0.85, 2)
    expect(hi[hi.length - 1]).toBeCloseTo(11 * 1.25, 2)
    expect(hi[2]).toBeGreaterThan(lo[2])
  })
  it('size key has one entry per departure class', () => {
    expect(sizeClasses(layer).map((c) => c.label)).toEqual(['<20', '20–50', '50–100', '100–200', '200+'])
    const r = sizeClasses(layer).map((c) => c.radius)
    expect(r).toEqual([...r].sort((a, b) => a - b))
    expect(r[0]).toBe(3)
    expect(r[4]).toBe(11)
  })
  it('fades the classes that are not emphasised, fill and stroke and rings', () => {
    expect(focusPaint(layer, new Set())).toEqual({ fill: 0.92, stroke: 1, ring: 0.9 })
    const f = focusPaint(layer, new Set([1]))
    expect(f.fill).toEqual(['step', ['get', 'walk_dir'], 0.12, 1, 0.92, 2, 0.12, 3, 0.12, 5, 0.12])
    expect(f.stroke).toEqual(['step', ['get', 'walk_dir'], 0.15, 1, 1, 2, 0.15, 3, 0.15, 5, 0.15])
    expect(f.ring).toBe(0.2)
  })
  it('a layer without a ramp has no specs', () => {
    expect(pointSpecs({ id: 'x', kind: 'points' })).toEqual([])
  })
  it('classes of a node follow the ramp', () => {
    expect([0.5, 1, 2.9, 5, 12].map((v) => classIndex(layer.ramp, v))).toEqual([0, 1, 2, 4, 4])
  })
})

describe('stop-area popup', () => {
  const p = {
    id: 'w-T1', agg: 'warszawa', name: 'Centrum', modes: 'bus,metro,tram', lines: 29, pairs: 804, pairs_excl: 12,
    dep_h: 313.4, dep_h_am: 340, walk_dir: 3.6, walk_dir_p90: 4.3, walk_best: 1.8, cross: 0.5, cross_signal: 0.59,
    steps: 0.83, stepfree: 0.5, wait_am: 5.3, wait_day: 6, walkwait_am: 8.8, walkwait_am_w: 5.7,
    walk_w: 2.64, wait_w: 5.66, walkwait_w: 8.3,
  }
  const rows = (m) => Object.fromEntries(m.sections.flatMap((s) => s.rows))
  it('groups the components under the Polish headings', () => {
    const m = nodePopupModel(p, '2026-11-25')
    expect(m.title).toBe('Centrum')
    expect(m.modes).toBe('autobus, metro, tramwaj')
    expect(m.sections.map((s) => s.title)).toEqual([
      'Typowa przesiadka', 'Znaczenie', 'Dojście (mediany)', 'Przeszkody', 'Czekanie (mediany)',
      'Dojście + czekanie 7–9 (mediany, nie sumują się z wierszami wyżej)',
    ])
    expect(m.sections[0].rows[0][0]).toBe(SUM_LABEL)
    const r = rows(m)
    expect(flat(r[SUM_LABEL])).toBe('dojście 2,6 min + czekanie 5,7 min = 8,3 min')
    expect(flat(r['7–9, mediana'])).toBe('5,3 min')
    expect(flat(r.Linie)).toBe('29')
    expect(flat(r['Pary przesiadkowe'])).toBe('804 (pominięto równoległych: 12)')
    expect(flat(r['Odjazdy na godzinę, 6–20'])).toBe('313,4')
    expect(flat(r['Z kierunkami, mediana'])).toBe('3,6 min')
    expect(flat(r['Przejścia z sygnalizacją'])).toBe('59 %')
    expect(flat(r['Ruchy ze schodami'])).toBe('83 %')
    expect(flat(r['Droga bez schodów w OSM'])).toBe('50 % ruchów')
    expect(flat(r['Najlepsza para, mediana ważona liczbą kursów'])).toBe('5,7 min')
    expect(m.notes).toEqual([])
    expect(m.footer).toBe('Rozkład 2026-11-25, OSM 2026-11-22; miara własna, składowe osobno')
  })
  it('prints missing values as "brak danych", never as zero, and explains a node outside the mask', () => {
    const m = nodePopupModel({ id: 'x', name: 'Poza', modes: 'bus', lines: 3, dep_h: 5.57, nodata: true, flag: 'dojście do punktu stacji' }, '2026-11-25')
    const r = rows(m)
    expect(r['Z kierunkami, mediana']).toBe(NO_DATA)
    expect(r['Pary przesiadkowe']).toBe(NO_DATA)
    expect(r['7–9, mediana']).toBe(NO_DATA)
    expect(r[SUM_LABEL]).toBe(NO_DATA)
    expect(flat(r.Linie)).toBe('3')
    expect(m.notes).toHaveLength(2)
    expect(num(0, 'min')).toBe('0 min')
    expect(num(null)).toBe(NO_DATA)
    expect(pct(0)).toBe('0 %')
    expect(pct(undefined)).toBe(NO_DATA)
  })
  it('the sum line always adds up in the printed digits', () => {
    // 1.04 + 1.04 = 2.08 would print as 2,1 if rounded on its own; the line prints the sum of the printed parts
    expect(flat(transferSumText(1.04, 1.04))).toBe('dojście 1 min + czekanie 1 min = 2 min')
    expect(flat(transferSumText(1.26, 2.26))).toBe('dojście 1,3 min + czekanie 2,3 min = 3,6 min')
    expect(transferSumText(1, null)).toBe(NO_DATA)
    expect(transferSumText(undefined, 2)).toBe(NO_DATA)
  })
  it('names the modes in Polish and keeps unknown ones', () => {
    expect(modesText('bus,rail,trolleybus')).toBe('autobus, kolej, trolejbus')
    expect(modesText('ferry')).toBe('ferry')
    expect(modesText(undefined)).toBe('')
  })
  it('builds the DOM from text only', () => {
    const m = nodePopupModel({ ...p, name: '<b>x</b>' }, null)
    const doc = { createElement: (tag) => ({ tag, className: '', textContent: '', children: [], appendChild(c) { this.children.push(c) } }) }
    const root = renderNodePopup(m, doc)
    expect(root.children[0].textContent).toBe('<b>x</b>')
    expect(root.children.at(-1).textContent).toBe('OSM 2026-11-22; miara własna, składowe osobno')
  })
})
