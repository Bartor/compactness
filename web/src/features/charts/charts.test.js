import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { atLeastReadout, fmtMin, fmtNum, fmtOutOfTen, fmtPct, fmtPts, NO_DATA } from './format'
import { bandPath, extent, keySet, linear, linePath, litKeys, median, nearestIndex, niceDomain, niceTicks, stepIndex } from './scales'
import {
  atLeastSeries, cityIds, dotStripRows, dumbbellRows, floorOf, headwaySeries, layerMarks, loadCharts, reachSeries,
  timeOfDayRows,
} from './data'
import AtLeastCurve, { classKeyOf, colouredKeys } from './AtLeastCurve'
import ReachCurve from './ReachCurve'
import DotStrip from './DotStrip'
import Dumbbell from './Dumbbell'
import TimeOfDay from './TimeOfDay'

const flat = (s) => s.replace(/ /g, ' ')

const dom = (k) => ({
  population: 1000, coverage_share: 0.98,
  at_least: { pt_am_30: [100, 80, 40, 10, 0], walk_30: [100, 95, 90, 50, 5] },
  headway_at_most: [10 + k, 40 + k, 60, 70, 80],
  floor: { 30: { floor: 16, below_floor: 10 + k, fgt1: 3, fgt2: 1.5, floors: [] }, 45: { below_floor: 5 + k } },
  palma: { 30: 0.7 },
  time_of_day: {
    pt_am_30: { ratio_of_means: 30 + k, p50: 29, below_floor: 10 + k }, pt_am_45: { ratio_of_means: 55 + k },
    pt_midday_30: { ratio_of_means: 28 + k }, pt_evening_30: { ratio_of_means: 25 + k, below_floor: 15 + k },
    pt_saturday_45: { ratio_of_means: 50 },
  },
  reach: { pt_am: { ratio_of_means: [10, 20, 35], mean_of_ratios: [9, 19, 33], p25: [5, 15, 25], p50: [9, 19, 34], p75: [14, 25, 45] } },
})
const FIX = {
  x_performance: [0, 25, 50, 75, 100], cutoffs_min: [15, 30, 45], headway_n_min: [5, 10, 15, 20, 30],
  windows: { pt_am: '7–9', pt_midday: 'południe', pt_evening: 'wieczór', pt_saturday: 'sobota' },
  floor: { floors: { 30: { 0.4: 12, 0.5: 16, 0.6: 19 } }, main_fraction: 0.5 },
  layer_marks: { transport_performance_30: { series: 'pt_am_30', stops: [10, 20, 30] } },
  cities: {
    gzm: { name: 'GZM', domains: { core: dom(5) } },
    warszawa: { name: 'Warszawa', domains: { core: dom(0), urban_centre: { time_of_day: { pt_am_30: { ratio_of_means: 37 } } } } },
    lodz: { name: 'Łódź', domains: { core: { ...dom(2), floor: {} } } },
  },
}

describe('format', () => {
  it('uses a decimal comma, no-break spaces and brak danych', () => {
    expect(flat(fmtPct(35.75, 1))).toBe('35,8 %')
    expect(flat(fmtNum(1234567))).toBe('1 234 567')
    expect(fmtNum(1234)).toBe('1234')
    expect(fmtPct(null)).toBe(NO_DATA)
    expect(fmtPct(Number.NaN)).toBe(NO_DATA)
    expect(flat(fmtMin(30))).toBe('30 min')
    expect(flat(fmtPts(-2.34))).toBe('−2,3 pkt')
    expect(flat(fmtPts(1))).toBe('+1,0 pkt')
    expect(fmtOutOfTen(62)).toBe('6 na 10')
  })
  it('writes the hover read-out of the at-least curve', () => {
    expect(flat(atLeastReadout(62.1, 30))).toBe('62 % mieszkańców ma co najmniej 30 %')
    expect(flat(atLeastReadout(45, 10, { unit: 'min', what: 'kursy' }))).toBe('45 % mieszkańców ma kursy co najmniej co 10 min')
    expect(flat(atLeastReadout(null, 30))).toBe('brak danych przy 30 %')
  })
})

describe('scales', () => {
  it('maps and inverts', () => {
    const s = linear([0, 100], [10, 210])
    expect(s(50)).toBe(110)
    expect(s.invert(110)).toBe(50)
    expect(linear([5, 5], [0, 10])(5)).toBe(5)
  })
  it('gives nice ticks', () => {
    expect(niceTicks(0, 100, 4)).toEqual([0, 25, 50, 75, 100])
    expect(niceTicks(0, 60, 4)).toEqual([0, 20, 40, 60])
    expect(niceTicks(3, 3)).toEqual([3])
    expect(niceTicks(Number.NaN, 1)).toEqual([])
    expect(niceDomain(0, 38, 4)).toEqual({ domain: [0, 40], ticks: [0, 10, 20, 30, 40] })
    expect(niceDomain(3.2, 9.1, 4).domain).toEqual([2, 10])
  })
  it('breaks lines at missing values and draws steps', () => {
    const id = (v) => v
    expect(linePath([0, 1, 2, 3], [1, null, 2, 3], id, id)).toBe('M0,1M2,2L3,3')
    expect(linePath([0, 1], [1, 2], id, id, { step: 'after' })).toBe('M0,1H1V2')
    expect(bandPath([0, 1], [0, 0], [1, 2], id, id)).toBe('M0,1L1,2L1,0L0,0Z')
    expect(bandPath([0, 1], [0, null], [1, 2], id, id)).toBe('')
  })
  it('finds the nearest point, the median and the extent', () => {
    expect(nearestIndex([0, 10, 20], 14)).toBe(1)
    expect(nearestIndex([], 1)).toBe(-1)
    expect(median([3, null, 1, 2])).toBe(2)
    expect(median([1, 2, 3, 4])).toBe(2.5)
    expect(median([null])).toBeNull()
    expect(extent([[1, null, 5], [3]])).toEqual([1, 5])
    expect(extent([[null]], [0, 9])).toEqual([0, 9])
  })
  it('handles key sets and arrow keys', () => {
    expect([...keySet(['a', 'b'])]).toEqual(['a', 'b'])
    expect(keySet(null).size).toBe(0)
    expect([...litKeys('x', new Set(['y']))].sort()).toEqual(['x', 'y'])
    expect(stepIndex('ArrowRight', -1, 5)).toBe(0)
    expect(stepIndex('ArrowLeft', -1, 5)).toBe(4)
    expect(stepIndex('ArrowRight', 4, 5)).toBe(4)
    expect(stepIndex('End', 1, 5)).toBe(4)
    expect(stepIndex('a', 1, 5)).toBeNull()
  })
})

describe('data selectors', () => {
  it('keeps the fixed city order', () => {
    expect(cityIds(FIX)).toEqual(['warszawa', 'lodz', 'gzm'])
  })
  it('builds the series', () => {
    const s = atLeastSeries(FIX, { aggs: ['gzm', 'lodz'], series: 'walk_30' })
    expect(s[0]).toMatchObject({ key: 'gzm', label: 'GZM', xs: [0, 25, 50, 75, 100] })
    expect(atLeastSeries(FIX, { aggs: ['lodz'], series: 'bike_lts3_30' })[0].ys).toBeNull()
    expect(headwaySeries(FIX, { aggs: ['gzm'] })[0].ys[0]).toBe(15)
    expect(reachSeries(FIX, { aggs: ['warszawa'] })[0].p75).toEqual([14, 25, 45])
  })
  it('gives dot strip rows with the median and missing values as null', () => {
    const d = dotStripRows(FIX, { measure: 'below_floor_30' })
    expect(d.rows.map((r) => r.value)).toEqual([10, null, 15])
    expect(d.median).toBe(12.5)
  })
  it('gives dumbbell and time-of-day rows', () => {
    const d = dumbbellRows(FIX, 'core_uc')
    expect(d.rows[0]).toMatchObject({ key: 'warszawa', a: 30, b: 37 })
    expect(d.rows[2]).toMatchObject({ key: 'gzm', a: 35, b: null })
    const t = timeOfDayRows(FIX, { agg: 'gzm' })
    expect(t.map((r) => r.key)).toEqual(['pt_am', 'pt_midday', 'pt_evening', 'pt_saturday'])
    expect(t[3]).toMatchObject({ v30: null, v45: 50, label: 'sobota' })
  })
  it('reads the floor and the layer marks', () => {
    expect(floorOf(FIX, 30)).toBe(16)
    expect(floorOf(FIX, 45)).toBeNull()
    expect(layerMarks(FIX, 'transport_performance_30').stops).toEqual([10, 20, 30])
    expect(layerMarks(FIX, 'nope')).toBeNull()
  })
  it('loads charts.json and swallows failures', async () => {
    const ok = await loadCharts({ base: 'x/', fetchImpl: async (u) => ({ ok: u === 'x/charts.json', json: async () => FIX }) })
    expect(ok.cities.gzm.name).toBe('GZM')
    expect(await loadCharts({ fetchImpl: async () => ({ ok: false }) })).toBeNull()
    expect(await loadCharts({ fetchImpl: async () => { throw new Error('offline') } })).toBeNull()
  })
})

describe('classes and colours', () => {
  it('maps a value to the class of the map legend', () => {
    expect(classKeyOf([10, 20, 30], 5)).toBe('c0')
    expect(classKeyOf([10, 20, 30], 10)).toBe('c1')
    expect(classKeyOf([10, 20, 30], 99)).toBe('c3')
    expect(classKeyOf([], 5)).toBeNull()
  })
  it('colours at most three series, the highlighted ones first', () => {
    const s = ['a', 'b', 'c', 'd'].map((key) => ({ key }))
    expect(colouredKeys(s.slice(0, 3))).toEqual(['a', 'b', 'c'])
    expect(colouredKeys(s, ['c'], 'a')).toEqual(['c', 'a'])
    expect(colouredKeys(s, ['a', 'b', 'c', 'd'])).toHaveLength(3)
  })
})

describe('components render (server markup)', () => {
  it('renders each chart with a table switch and accessible names', () => {
    const html = [
      h(AtLeastCurve, { series: atLeastSeries(FIX), highlight: ['gzm'], marks: [10, 20, 30], floor: 16, hot: 'c1' }),
      h(AtLeastCurve, { series: headwaySeries(FIX), unit: 'min', what: 'kursy' }),
      h(ReachCurve, { series: reachSeries(FIX), focus: 'warszawa' }),
      h(DotStrip, { ...dotStripRows(FIX), selected: 'gzm', better: 'low' }),
      h(Dumbbell, { ...dumbbellRows(FIX, '30v45'), title: 'x' }),
      h(TimeOfDay, { rows: timeOfDayRows(FIX, { agg: 'gzm' }) }),
    ].map((e) => renderToStaticMarkup(e))
    for (const s of html) {
      expect(s).toContain('aria-pressed="false"')
      expect(s).toContain('role="img"')
      expect(s).toContain('tabindex="0"')
      expect(s).not.toContain('NaN')
    }
    expect(html[0]).toContain('próg')
    expect(html[3]).toContain(NO_DATA)
  })
})

// the real file, when the pipeline has written it (skipped otherwise)
const real = resolve(__dirname, '../../../../results/web/charts.json')
describe.skipIf(!existsSync(real))('results/web/charts.json', () => {
  const c = JSON.parse(readFileSync(real, 'utf-8'))
  it('has seven cities with curves that start at 100 % and never rise', () => {
    expect(cityIds(c)).toHaveLength(7)
    for (const s of atLeastSeries(c, { series: 'pt_am_30' })) {
      expect(s.ys[0]).toBe(100)
      for (let i = 1; i < s.ys.length; i++) expect(s.ys[i]).toBeLessThanOrEqual(s.ys[i - 1])
    }
    expect(floorOf(c, 30)).toBe(16)
    expect(dotStripRows(c).rows.every((r) => r.value != null)).toBe(true)
    const html = renderToStaticMarkup(h(AtLeastCurve, { series: atLeastSeries(c), highlight: ['gzm'] }))
    expect(html).not.toContain('NaN')
  })
})
