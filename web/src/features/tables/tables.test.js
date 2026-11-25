import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { METRIC_INFO } from '../../metricInfo'
import { indexMetrics } from '../../metricTable'
import { readHash, hashOf, resolveHash } from '../../urlState'
import { buildTable } from './buildTable'
import MeasurePicker from './MeasurePicker'
import TableBuilder from './TableBuilder'
import { OWN_KEY, readOwn, writeOwn } from './storage'
import {
  DEFAULT_TABLE, NAJWAZNIEJSZE, areasOf, citiesMode, citiesOf, needsTimetable, normalizeTable, parseTableKeys, selectionOf, shapeOf,
  tableFromKeys, toggleArea, writeTableKeys,
} from './spec'

const noop = () => {}
const row = (agglomeration, metric, domain, value, extra = {}) => ({ agglomeration, metric, domain, value, unit: '%', label: `L ${metric}`, tier: 'main', ...extra })
const TT = ['a', 'b', 'c']
const EVERY = ['a', 'b', 'c', 'd']   // d has no timetables
const names = { a: 'Aaa', b: 'Bbb', c: 'Ccc', d: 'Ddd' }
const index = indexMetrics([
  ...EVERY.map((c, i) => row(c, 'pwdens_census_1km', 'core', 5000 + i, { unit: 'os./km²' })),
  ...EVERY.map((c, i) => row(c, 'pwdens_census_1km', 'fua', 3000 + i, { unit: 'os./km²' })),
  ...TT.map((c, i) => row(c, 'tp_pt_am_30min_ratio_of_means', 'core', 20 + i)),
  ...TT.map((c, i) => row(c, 'tp_pt_am_30min_ratio_of_means', 'covered', 10 + i)),
  ...TT.map((c, i) => row(c, 'tram_speed_median', 'city_tram_network', 15 + i, { unit: 'km/h' })),
  row('a', 'area', 'core', null),
])
const ctx = { agg: null, everyCity: EVERY, transport: TT, index }
const build = ({ set = 'all', ids = [], cities, areas, swap = false, grouped = false }) => buildTable({
  index, selection: selectionOf({ set, ids }, index), cities, areas, shape: shapeOf(cities, areas, swap), names, layers: [],
  onShowLayer: noop, transport: TT, everyCity: EVERY, grouped,
})

describe('the presets', () => {
  it('"Najważniejsze" lists ten measures that all have a description', () => {
    expect(NAJWAZNIEJSZE).toHaveLength(10)
    for (const id of NAJWAZNIEJSZE) expect(METRIC_INFO[id]?.short, id).toBeTruthy()
  })
  it('selects the story measures in their order (one list), a group, everything, or a hand-made list; unknown ids are dropped', () => {
    const story = selectionOf(DEFAULT_TABLE, index)
    expect(story.ids).toEqual(['pwdens_census_1km', 'tp_pt_am_30min_ratio_of_means', 'tram_speed_median'])
    expect(story.flat).toBe(true)
    expect(selectionOf({ set: 'all' }, index).groups.length).toBeGreaterThan(1)
    expect(selectionOf({ set: 'reach' }, index).ids).toEqual(['tp_pt_am_30min_ratio_of_means'])
    const own = selectionOf({ set: 'own', ids: ['tram_speed_median', 'nope', 'pwdens_census_1km'] }, index)
    expect(own.ids).toEqual(['pwdens_census_1km', 'tram_speed_median'])   // the order of the groups, not of the click
    expect(selectionOf({ set: 'own', ids: ['nope'] }, index).ids).toEqual([])
  })
})

describe('which cities and areas', () => {
  it('uses the cities with timetables when a chosen measure needs them, else all, and every city for "Wszystkie"', () => {
    const story = selectionOf(DEFAULT_TABLE, index)
    expect(citiesOf(DEFAULT_TABLE, { ...ctx, ids: story.ids })).toEqual(TT)
    expect(citiesOf({ set: 'own', ids: [] }, { ...ctx, ids: ['pwdens_census_1km'] })).toEqual(EVERY)
    expect(citiesOf({ set: 'all' }, { ...ctx, ids: story.ids })).toEqual(EVERY)
    expect(citiesOf({ ...DEFAULT_TABLE, cities: 'all' }, { ...ctx, ids: story.ids })).toEqual(EVERY)
    expect(citiesOf({ ...DEFAULT_TABLE, cities: ['c', 'a', 'zz'] }, { ...ctx, ids: story.ids })).toEqual(['a', 'c'])
    expect(citiesOf(DEFAULT_TABLE, { ...ctx, agg: 'd', ids: story.ids })).toEqual(['d'])
    expect(needsTimetable(index, 'tp_pt_am_30min_ratio_of_means', ['d'])).toBe(true)
    expect(needsTimetable(index, 'pwdens_census_1km', ['d'])).toBe(false)
    expect(citiesMode(TT, ctx)).toBe('tt')
    expect(citiesMode(['a', 'b'], ctx)).toBe('pick')
  })
  it('follows the header\'s area unless the reader chose some, in a city too', () => {
    expect(areasOf(DEFAULT_TABLE, { globalArea: 'fua' })).toEqual({ areas: ['fua'], following: true })
    expect(areasOf({ ...DEFAULT_TABLE, areas: ['fua', 'core'] }, { globalArea: 'core' }).areas).toEqual(['fua', 'core'])
    expect(areasOf(DEFAULT_TABLE, { globalArea: 'core', agg: 'a' })).toEqual({ areas: ['core'], following: true })
    expect(toggleArea(['core'], 'fua')).toEqual(['core', 'fua'])
    expect(toggleArea(['core'], 'core')).toBeNull()   // nothing chosen: back to following the header
  })
  it('chooses the shape from the number of cities and areas', () => {
    expect(shapeOf(TT, ['core']).key).toBe('cities')
    expect(shapeOf(['a'], ['core', 'fua']).key).toBe('areas')
    expect(shapeOf(TT, ['core', 'fua']).key).toBe('subarea')
    expect(shapeOf(TT, ['core', 'fua'], true).key).toBe('subcity')
    expect(shapeOf(['a'], ['core']).key).toBe('value')
    expect(shapeOf(TT, ['core'], true).key).toBe('cities')     // nothing to swap
    expect(shapeOf(TT, ['core', 'fua']).canSwap).toBe(true)
  })
})

describe('the address', () => {
  const q = (s) => new URLSearchParams(s)
  it('writes only what differs from the default and reads it back', () => {
    const w = (t) => { const p = new URLSearchParams(); writeTableKeys(p, t); return p.toString().replace(/%2C/g, ',') }
    expect(w(DEFAULT_TABLE)).toBe('')
    expect(w({ ...DEFAULT_TABLE, set: 'reach' })).toBe('tb=reach')
    expect(w({ set: 'own', ids: ['area', 'rho_t20'], cities: 'all', areas: ['core', 'fua'], swap: true })).toBe('tb=area,rho_t20&tc=all&ta=core,fua&tx=1')
    expect(parseTableKeys(q(''))).toBeNull()
    expect(parseTableKeys(q('tb=all'))).toEqual({ set: 'all' })
    expect(parseTableKeys(q('tb=area,rho_t20&tc=a,b&ta=fua,zzz&tx=1'))).toEqual({ set: 'own', ids: ['area', 'rho_t20'], cities: ['a', 'b'], areas: ['fua'], swap: true })
    expect(tableFromKeys(parseTableKeys(q('tb=area&tc=tt')))).toEqual({ set: 'own', ids: ['area'], cities: 'tt', areas: null, swap: false })
  })
  it('is part of the page address and ignores ids that do not exist', () => {
    const state = { set: 'own', ids: ['pwdens_census_1km', 'gone'], cities: ['a', 'b'], areas: null, swap: false }
    const hash = hashOf({ layers: [], table: state }, { layers: [] })
    expect(hash).toBe('#tb=pwdens_census_1km,gone&tc=a,b')
    const back = tableFromKeys(resolveHash(readHash(hash), { agglomerations: [], layers: [] }).table)
    expect(back).toEqual(state)
    expect(selectionOf(back, index).ids).toEqual(['pwdens_census_1km'])
    expect(tableFromKeys(readHash('#tb=%E2%80%A6&tc=&ta=x').table).areas).toBeNull()
  })
  it('normalizes a state with odd parts', () => {
    expect(normalizeTable({ set: 'zzz', ids: ['a'], cities: [], areas: ['x'] })).toEqual(DEFAULT_TABLE)
  })
})

describe('the hand-made selection in the browser', () => {
  const store = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: (k) => m.delete(k) } }
  it('is kept under a key of this project, and survives a storage that is blocked or holds rubbish', () => {
    expect(OWN_KEY.startsWith('compactness-')).toBe(true)
    const s = store()
    writeOwn(['a', 'b'], s)
    expect(readOwn(s)).toEqual(['a', 'b'])
    writeOwn([], s)
    expect(readOwn(s)).toEqual([])
    s.setItem(OWN_KEY, '{not json')
    expect(readOwn(s)).toEqual([])
    const blocked = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') }, removeItem() { throw new Error('blocked') } }
    expect(readOwn(blocked)).toEqual([])
    expect(() => writeOwn(['a'], blocked)).not.toThrow()
  })
})

describe('the rows of the table', () => {
  const rowsOf = (m) => m.groups.flatMap((g) => g.rows)
  it('cities in columns: marks the best, puts "–" for a city without timetables, says it once in lackTimetable', () => {
    const m = build({ cities: EVERY, areas: ['core'] })
    expect(m.shape).toBe('cities')
    const reach = rowsOf(m).find((r) => r.id === 'tp_pt_am_30min_ratio_of_means')
    expect(reach.cells.map((c) => c.content)).toEqual(['20,0', '21,0', '22,0', '–'])
    expect(reach.cells[2].tone).toBe('best')
    expect(reach.cells[3].title).toContain('rozkładach')
    expect(m.lackTimetable).toEqual(['d'])
    expect(build({ cities: TT, areas: ['core'] }).lackTimetable).toEqual([])
  })
  it('leaves out a measure that has no figure anywhere and counts it; a missing figure is never 0', () => {
    const m = build({ cities: ['a'], areas: ['core'], set: 'own', ids: ['area', 'pwdens_census_1km'] })
    expect(rowsOf(m).map((r) => r.id)).toEqual(['pwdens_census_1km'])
    expect(m.hidden).toBe(1)
    expect(rowsOf(build({ cities: TT, areas: ['core'], set: 'reach' })).length).toBe(1)
    expect(build({ cities: ['d'], areas: ['core'], set: 'reach' }).rowCount).toBe(0)
  })
  it('reads a measure in the nearest area when the asked one has none, and says so', () => {
    const m = build({ cities: TT, areas: ['urban_centre'], set: 'own', ids: ['pwdens_census_1km'] })
    const r = rowsOf(m)[0]
    expect(r.movedTo).toBe('core')
    expect(r.unit).toContain('obszar: Miasto')
    expect(m.moved).toBe(true)
  })
  it('one city in several areas: the areas are the columns and the tram network stands in the first one only', () => {
    const m = build({ cities: ['a'], areas: ['core', 'covered', 'fua'] })
    expect(m.columns.map((c) => c.key)).toEqual(['core', 'covered', 'fua'])
    const reach = rowsOf(m).find((r) => r.id === 'tp_pt_am_30min_ratio_of_means')
    expect(reach.cells.map((c) => c.content)).toEqual(['20,0', '10,0', '–'])
    const tram = rowsOf(m).find((r) => r.id === 'tram_speed_median')
    expect(tram.cells.map((c) => c.content)).toEqual(['15', '', ''])
    expect(tram.cells[0].content).not.toBe('0')
  })
  it('several cities and areas: a sub-row per area under the measure, cities in columns; swapped, a sub-row per city', () => {
    const m = build({ cities: TT, areas: ['core', 'covered', 'fua'], set: 'own', ids: ['tp_pt_am_30min_ratio_of_means', 'tram_speed_median'] })
    expect(rowsOf(m).map((r) => r.id)).toEqual(['tram_speed_median', 'tp_pt_am_30min_ratio_of_means~core', 'tp_pt_am_30min_ratio_of_means~covered'])
    const [, first, second] = rowsOf(m)
    expect(first.help).toBeTruthy()      // the "?" and the actions only once per measure
    expect(second.help).toBeUndefined()
    expect(renderToStaticMarkup(h('div', null, second.label))).toContain('tb-sub')
    const swapped = build({ cities: ['a', 'b'], areas: ['core', 'covered'], swap: true, set: 'reach' })
    expect(swapped.columns.map((c) => c.key)).toEqual(['core', 'covered'])
    expect(rowsOf(swapped).map((r) => r.id)).toEqual(['tp_pt_am_30min_ratio_of_means~a', 'tp_pt_am_30min_ratio_of_means~b'])
  })
  it('one city in one area: the value and the rank', () => {
    const m = build({ cities: ['a'], areas: ['core'], set: 'reach' })
    expect(m.columns.map((c) => c.key)).toEqual(['v', 'pos'])
    expect(rowsOf(m)[0].cells[1].content).toBe('3/3')
  })
  it('puts the divider between the cities with and without timetables only when asked and when both kinds are shown', () => {
    expect(build({ cities: EVERY, areas: ['core'], grouped: true }).columns.some((c) => c.key === '__gap')).toBe(true)
    expect(build({ cities: EVERY, areas: ['core'], grouped: false }).columns.some((c) => c.key === '__gap')).toBe(false)
    expect(build({ cities: TT, areas: ['core'], grouped: true }).columns.some((c) => c.key === '__gap')).toBe(false)
  })
})

describe('the component', () => {
  const props = {
    index, everyCity: EVERY, transport: TT, names, globalArea: 'core', table: DEFAULT_TABLE, onTable: noop, layers: [], onShowLayer: noop,
    onOpenMetric: noop, onPickCity: noop, hot: null, setHot: noop, onOpenLimits: noop,
  }
  const html = (extra) => renderToStaticMarkup(h(TableBuilder, { ...props, ...extra }))
  it('is a bar with the presets, the cities and the areas over the table, with the sort line always there', () => {
    const s = html({})
    for (const t of ['Najważniejsze', 'Wszystkie', 'Własny', 'Wybierz miary', '3 z rozkładami', 'Wszystkie 4', 'Centrum miejskie', 'jak u góry', 'Zamień wiersze i kolumny', 'Kolejność: domyślna']) {
      expect(s, t).toContain(t)
    }
    expect(s).toContain('kit-data-table')
  })
  it('says what to do when nothing is selected, and when the preset has no figures for the cities', () => {
    expect(html({ table: { ...DEFAULT_TABLE, set: 'own' } })).toContain('Wybierz miary, aby zobaczyć tabelę')
    expect(html({ table: { ...DEFAULT_TABLE, set: 'reach', cities: ['d'] } })).toContain('Brak danych o rozkładach jazdy: Ddd')
  })
  it('in a city view starts from the city with the four areas as columns', () => {
    const s = html({ agg: 'a' })
    expect(s).toContain('Aaa')
    expect((s.match(/class="kit-data-col"/g) || []).length).toBeGreaterThanOrEqual(3)
  })
  it('the picker lists the groups with "cała grupa", the names, a count and the buttons', () => {
    const s = renderToStaticMarkup(h(MeasurePicker, { index, ids: ['area'], onChange: noop, onClose: noop }))
    for (const t of ['cała grupa', 'wybrano 1 z', 'Wyczyść', 'Gotowe', 'Szukaj miary']) expect(s, t).toContain(t)
    expect(s).toContain('type="checkbox"')
  })
})
