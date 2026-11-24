import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import {
  cityValues, densityBars, directionBadge, medianOf, neighbours, pageAreas, pageFromHash, pageText, partnerOf, pickArea,
  ranks, reachBase, relatedBlocks, rowsOf, sourceFacts, universe, walkOrder,
} from './metricPageData'
import { indexMetrics } from './metricTable'
import { readHash, resolveHash, hashOf } from './urlState'
import { rowActions, pageAction, cityGroups, compareGroups } from './tableModel'
import MetricHelp from './MetricHelp'
import MetricPage from './MetricPage'

const row = (agglomeration, metric, domain, value, extra = {}) => ({
  agglomeration, metric, domain, value, unit: '%', label: `L ${metric}`, tier: 'main', ...extra,
})
const rows = [
  row('a', 'tp_pt_am_30min_ratio_of_means', 'core', 30, { source: 'R5', timetable_date: '2026-11-25', population_grid: 'ghsl_census_scaled', feed_variant: 'all', coverage_share: 0.9, flag: 'uwaga' }),
  row('b', 'tp_pt_am_30min_ratio_of_means', 'core', 20, { source: 'R5', timetable_date: '2026-11-25', coverage_share: 0.8 }),
  row('c', 'tp_pt_am_30min_ratio_of_means', 'core', null),
  row('a', 'tp_pt_am_30min_ratio_of_means', 'urban_centre', 35),
  row('a', 'tp_pt_am_30min', 'core', 28), row('b', 'tp_pt_am_30min', 'core', 18),
  row('a', 'tp_pt_am_45min_ratio_of_means', 'core', 50), row('b', 'tp_pt_am_45min_ratio_of_means', 'core', 40),
  row('a', 'area', 'core', 100, { unit: 'km²' }), row('d', 'area', 'core', 50, { unit: 'km²' }),
  row('a', 'tram_speed_median', 'city_tram_network', 17, { unit: 'km/h' }),
]
const index = indexMetrics(rows)

describe('metric page data', () => {
  it('has the areas where the metric has a number, in chip order, and picks one', () => {
    const id = 'tp_pt_am_30min_ratio_of_means'
    expect(pageAreas(index, id)).toEqual(['core', 'urban_centre'])
    expect(pageAreas(index, 'tram_speed_median')).toEqual(['city_tram_network'])
    expect(pickArea(index, id, 'urban_centre')).toBe('urban_centre')
    expect(pickArea(index, id, 'fua')).toBe('core')
    expect(pickArea(index, 'tram_speed_median', 'core')).toBe('city_tram_network')
    expect(pickArea(index, 'nothing', 'core')).toBeNull()
  })
  it('lists cities with a value and those without, never as zero, and uses all cities only for density metrics', () => {
    const v = cityValues(index, 'tp_pt_am_30min_ratio_of_means', 'core', ['a', 'b', 'c', 'x'])
    expect(v.have.map((x) => [x.id, x.value])).toEqual([['a', 30], ['b', 20]])
    expect(v.missing).toEqual(['c', 'x'])
    expect(universe(index, 'area', ['a', 'b', 'd'], ['a', 'b'])).toEqual(['a', 'b', 'd'])
    expect(universe(index, 'tp_pt_am_30min', ['a', 'b', 'd'], ['a', 'b'])).toEqual(['a', 'b'])
  })
  it('ranks by the direction, ties share the better place, and takes the median', () => {
    const have = [{ id: 'a', value: 10 }, { id: 'b', value: 30 }, { id: 'c', value: 30 }]
    expect(ranks(have, 'higher')).toEqual({ a: 3, b: 1, c: 1 })
    expect(ranks(have, 'lower')).toEqual({ a: 1, b: 2, c: 2 })
    expect(medianOf([1, 3, null, 2])).toBe(2)
    expect(medianOf([1, 2, 3, 4])).toBe(2.5)
    expect(medianOf([])).toBeNull()
  })
  it('walks the visible order of the table across groups, with neighbours and the group', () => {
    const order = walkOrder(index)
    const ids = order.map((o) => o.id)
    expect(ids.indexOf('area')).toBeLessThan(ids.indexOf('tram_speed_median'))
    expect(ids.indexOf('tram_speed_median')).toBeLessThan(ids.indexOf('tp_pt_am_30min_ratio_of_means'))
    const n = neighbours(order, 'tram_speed_median')
    expect(n.prev).toBe('area')
    expect(n.next).toBe('tp_pt_am_30min_ratio_of_means')
    expect(n.groupTitle).toBe('Oferta komunikacji')
    expect(neighbours(order, ids[0]).prev).toBeNull()
    expect(neighbours(order, ids[ids.length - 1]).next).toBeNull()
    expect(neighbours(order, 'zzz')).toBeNull()
  })
})

describe('related blocks', () => {
  const types = (id) => relatedBlocks(id).map((b) => b.type + (b.series ? `:${b.series}` : '') + (b.mode ? `:${b.mode}` : '') + (b.pair ? `:${b.pair}` : ''))
  it('maps reach metrics to the twin, the 30/45 pair, the curve, the reach curve and the time of day', () => {
    expect(types('tp_pt_am_30min_ratio_of_means')).toEqual(['twin', 'pair30v45', 'atleast:pt_am_30', 'reach:pt_am', 'timeofday'])
    expect(types('tp_pt_am_45min')).toEqual(['twin', 'pair30v45', 'atleast:pt_am_45', 'reach:pt_am', 'timeofday'])
    expect(types('tp_walk_30min')).toEqual(['twin', 'pair30v45', 'atleast:walk_30', 'reach:walk'])
    expect(types('tp_bike_lts3_30min_ratio_of_means')).toContain('reach:bike_lts3')
  })
  it('maps frequency, distribution and density metrics, and nothing for others', () => {
    expect(types('freq_seg_net_le10min')).toEqual(['headway'])
    expect(types('dist_below_floor_pt_am_30min')).toEqual(['atleast:pt_am_30', 'dumbbell:peak_evening_floor'])
    expect(types('dist_below_floor_pt_am_45min')[0]).toBe('atleast:pt_am_45')
    expect(types('dist_p25_pt_am_30min')).toEqual(['atleast:pt_am_30'])
    expect(relatedBlocks('dist_below_floor_pt_am_30min')[0].floor).toBe(30)
    expect(types('share_residents_ge5000')).toEqual(['density'])
    expect(types('median_resident_density_250m')).toEqual(['density'])
    expect(types('area')).toEqual([])
    expect(types('unknown_thing')).toEqual([])
  })
  it('finds the partner row of a twin and of 30 vs 45 min', () => {
    expect(partnerOf('tp_pt_am_30min_ratio_of_means', 'twin')).toMatchObject({ a: 'tp_pt_am_30min_ratio_of_means', b: 'tp_pt_am_30min' })
    expect(partnerOf('tp_pt_am_30min', 'twin')).toMatchObject({ a: 'tp_pt_am_30min_ratio_of_means', b: 'tp_pt_am_30min' })
    expect(partnerOf('tp_pt_am_30min_ratio_of_means', 'pair30v45')).toMatchObject({ a: 'tp_pt_am_30min_ratio_of_means', b: 'tp_pt_am_45min_ratio_of_means' })
    expect(partnerOf('tp_pt_am_45min', 'pair30v45')).toMatchObject({ a: 'tp_pt_am_30min', b: 'tp_pt_am_45min' })
    expect(partnerOf('tp_walk_30min', 'pair30v45').b).toBe('tp_walk_45min')
    expect(reachBase('x_ratio_of_means')).toBe('x')
  })
})

describe('text and sources', () => {
  it('splits the prose: the first paragraph leads, the uncertainty sentence stands apart, gaps are listed', () => {
    const info = { m: { read: ['Pierwszy.', 'Drugi.', 'Niepewność: coś.'], method: ['Metoda.'] }, n: { read: [], method: [] } }
    expect(pageText('m', info)).toMatchObject({ lead: 'Pierwszy.', read: ['Drugi.'], uncertainty: ['Niepewność: coś.'], method: ['Metoda.'], gaps: [] })
    expect(pageText('n', info).gaps).toEqual(['jak czytać', 'jak policzono'])
    expect(pageText('zzz', info)).toMatchObject({ lead: null, gaps: ['opis miary'] })
    const real = pageText('tp_pt_am_30min_ratio_of_means')
    expect(real.lead).toBeTruthy()
    expect(real.uncertainty.length).toBe(1)
  })
  it('badges the direction', () => {
    expect(directionBadge('higher')).toBe('wyżej = lepiej')
    expect(directionBadge('lower')).toBe('niżej = lepiej')
    expect(directionBadge(null)).toBeNull()
  })
  it('lists each distinct source fact once, in plain Polish, only for fields the rows carry', () => {
    const f = sourceFacts(rowsOf(index, 'tp_pt_am_30min_ratio_of_means'))
    const by = Object.fromEntries(f.map((x) => [x.label, x.values]))
    expect(by['Źródło']).toEqual(['R5'])
    expect(by['Data rozkładów jazdy']).toEqual(['2026-11-25'])
    expect(by['Dane o ludności']).toEqual(['GHSL 250 m przeskalowany do spisu 1 km'])
    expect(by['Wersja rozkładów jazdy']).toEqual(['wszystkie feedy, w tym nieoficjalne'])
    expect(by['Pokrycie danymi o rozkładach'].length).toBe(2)
    expect(by['Uwagi']).toEqual(['uwaga'])
    expect(by['Data danych o ludności']).toBeUndefined()
    expect(sourceFacts([])).toEqual([])
  })
  it('builds density-class bars from form.json: core or whole area, only cities in the file', () => {
    const form = {
      classes: [{ label: '< 500' }, { label: '500+' }],
      cities: [
        { id: 'a', name: 'Aaa', core: { share: [0.4, 0.6] }, fua: { share: [0.7, 0.3] } },
        { id: 'b', name: 'Bbb', core: { share: [0.1, 0.9] }, fua: { share: [0.2, 0.8] } },
      ],
    }
    const core = densityBars(form, ['b', 'a', 'zzz'], 'core', ['#111', '#222'])
    expect(core.map((r) => r.key)).toEqual(['b', 'a'])
    expect(core[1].parts.map((p) => [p.label, p.color, p.share])).toEqual([['< 500', '#111', 0.4], ['500+', '#222', 0.6]])
    expect(densityBars(form, ['a'], 'fua', [])[0].parts[0].share).toBe(0.7)
    expect(densityBars(null, ['a'], 'core', [])).toEqual([])
  })
})

describe('the address of a metric page', () => {
  it('writes m= and ma= (not for the core), reads them back, and leaves old addresses alone', () => {
    expect(hashOf({ agg: null, layers: [], metric: 'area' }, { layers: [] })).toBe('#m=area')
    expect(hashOf({ agg: null, layers: [], metric: 'area', metricArea: 'fua' }, { layers: [] })).toBe('#m=area&ma=fua')
    expect(hashOf({ agg: null, layers: [], metric: 'area', metricArea: 'core' }, { layers: [] })).toBe('#m=area')
    expect(hashOf({ agg: null, layers: [], metricArea: 'fua' }, { layers: [] })).toBe('')
    const r = readHash('#a=lodz&m=area&ma=fua')
    expect(r).toMatchObject({ agg: 'lodz', metric: 'area', metricArea: 'fua' })
    const cat = { agglomerations: [{ id: 'lodz' }], layers: [] }
    expect(resolveHash(r, cat)).toMatchObject({ metric: 'area', metricArea: 'fua' })
    expect(resolveHash(readHash('#a=lodz'), cat)).toMatchObject({ metric: null, metricArea: null })
    expect(pageFromHash('area', 'fua', index)).toEqual({ id: 'area', area: 'core' })
    expect(pageFromHash('zzz', null, index)).toBeNull()
  })
})

describe('opening the page from the tables', () => {
  const noop = () => {}
  const layers = [{ id: 'density_250m', status: 'ready', kind: 'choropleth' }]
  it('gives a row the map and page actions (map first, then the page) in `actions` only', () => {
    expect(pageAction('area', null)).toBeNull()
    const a = rowActions({ area: {} }, 'area', layers, noop, noop)
    expect(a.actions.map((x) => x.label)).toEqual(['strona miary'])
    expect(a.action).toBeUndefined()
    const b = rowActions({ area: { layer: 'density_250m' } }, 'area', layers, noop, noop)
    expect(b.actions.map((x) => x.label)).toEqual(['na mapie', 'strona miary'])
    const none = rowActions({}, 'area', layers, noop, null)
    expect(none.actions).toBeUndefined()
  })
  it('the comparison rows carry the actions, the city table label is a button, and the "?" ends with the link', () => {
    const groups = compareGroups({ index, cities: ['a', 'b'], area: 'core', names: {}, layers, onShowLayer: noop, onOpenMetric: noop })
    const r = groups.flatMap((g) => g.rows).find((x) => x.id === 'area')
    expect(r.actions.map((x) => x.label)).toContain('strona miary')
    const cg = cityGroups({ index, cities: ['a', 'b'], agg: 'a', layers, onShowLayer: noop, onOpenMetric: noop })
    const cr = cg.flatMap((g) => g.rows).find((x) => x.id === 'area')
    expect(renderToStaticMarkup(h('div', null, cr.label))).toContain('metric-link')
    expect(cr.name).toBe('Powierzchnia')
    const plain = cityGroups({ index, cities: ['a', 'b'], agg: 'a', layers, onShowLayer: noop })
    expect(typeof plain.flatMap((g) => g.rows).find((x) => x.id === 'area').label).toBe('string')
    expect(renderToStaticMarkup(h(MetricHelp, { id: 'area', entries: [], nameOf: (x) => x, onOpen: noop }))).toContain('Otwórz stronę miary')
    expect(renderToStaticMarkup(h(MetricHelp, { id: 'area', entries: [], nameOf: (x) => x }))).not.toContain('Otwórz stronę miary')
  })
})

describe('the metric page renders', () => {
  const noop = () => {}
  const link = { hot: null, setHot: noop, pinned: [], onPin: noop }
  const base = {
    area: 'core', setArea: noop, from: 'a', index, cities: ['a', 'b', 'c'], everyCity: ['a', 'b', 'c', 'd'], names: { a: 'Aaa', b: 'Bbb', c: 'Ccc', d: 'Ddd' },
    charts: null, form: null, densityColors: [], layers: [{ id: 'density_250m', status: 'ready' }], link, onClose: noop, onNavigate: noop,
    onPickCity: noop, onShowLayer: noop,
  }
  it('has the heading, the lead before the chart, the badge, the missing cities, the areas table and the sources', () => {
    const s = renderToStaticMarkup(h(MetricPage, { ...base, id: 'tp_pt_am_30min_ratio_of_means' }))
    expect(s).toContain('<h1>')
    expect(s).toContain('wyżej = lepiej')
    expect(s.indexOf('metric-lead')).toBeLessThan(s.indexOf('chx-rankbars'))
    expect(s).toContain('brak danych: Ccc')
    expect(s).toContain('Obszary obok siebie')
    expect(s).toContain('Źródła i daty')
    expect(s).toContain('Jak policzono')
    expect(s).toContain('Niepewność')
    expect(s).toContain('← wróć')
    expect(s).toContain('Centrum miejskie')
    expect(s).toContain('metric-city')
    expect(s).not.toContain('Pokaż na mapie')   // this metric has no layer in this catalog
    expect(s).toContain('Powiązane')   // the twin dumbbell has data
  })
  it('shows the map button for a metric with a ready layer, and no empty related section otherwise', () => {
    const withoutRelated = renderToStaticMarkup(h(MetricPage, { ...base, id: 'area', area: 'core' }))
    expect(withoutRelated).not.toContain('Powiązane')
    expect(withoutRelated).toContain('Ddd')   // a density metric lists all cities
    const idx2 = indexMetrics([...rows, row('a', 'pwdens_census_1km', 'core', 5000, { unit: 'os./km²' })])
    const s = renderToStaticMarkup(h(MetricPage, { ...base, index: idx2, id: 'pwdens_census_1km', layers: [{ id: 'density_250m', status: 'ready' }] }))
    expect(s).toContain('Pokaż na mapie')
  })
  it('copes with a metric without a text and without any value', () => {
    const idx2 = indexMetrics([row('a', 'mystery', 'core', 3, { label: 'Tajemnicza' })])
    const s = renderToStaticMarkup(h(MetricPage, { ...base, index: idx2, id: 'mystery' }))
    expect(s).toContain('Tajemnicza')
    expect(s).toContain('Brak tekstu')
    expect(() => renderToStaticMarkup(h(MetricPage, { ...base, id: 'nonexistent' }))).not.toThrow()
  })
})
