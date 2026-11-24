import { describe, expect, it } from 'vitest'
import { hashOf, readHash, resolveHash } from './urlState'
import { classLabel, rampClasses, rampExpression, rampLegend } from './ramp'
import { formatValue, groupMetrics, metricNotes, NO_DATA } from './metrics'
import { absoluteUrl, resolveUrl } from './config'
import { hatchImage } from './mapStyle'
import { layerSpecs, sourceSpec } from './mapLayers'
import { legendRows } from './layerInfo'
import { activeIds } from './layerControl'

const flat = (s) => s.replace(/\u00a0/g, ' ')

describe('url state', () => {
  const catalog = {
    agglomerations: [{ id: 'wroclaw' }, { id: 'lodz' }],
    layers: [
      { id: 'fua', kind: 'boundary', status: 'ready' }, { id: 'd', kind: 'choropleth', status: 'planned' },
      { id: 'x', kind: 'future', status: 'ready' },
    ],
  }
  it('reads agglomeration and layers', () => {
    expect(readHash('#a=wroclaw&l=fua,x')).toMatchObject({ agg: 'wroclaw', layers: ['fua', 'x'], variants: {}, pinned: [] })
    expect(readHash('')).toMatchObject({ agg: undefined, layers: undefined, variants: {}, pinned: [] })
    expect(readHash('#l=').layers).toEqual([])
  })
  it('writes only what differs from the defaults', () => {
    const d = { layers: ['fua'] }
    expect(hashOf({ agg: null, layers: ['fua'] }, d)).toBe('')
    expect(hashOf({ agg: 'lodz', layers: ['fua'] }, d)).toBe('#a=lodz')
    expect(hashOf({ agg: 'lodz', layers: ['x', 'fua'] }, d)).toBe('#a=lodz&l=fua,x')
    expect(hashOf({ agg: null, layers: [] }, d)).toBe('#l=')
  })
  it('round-trips', () => {
    const d = { layers: ['fua'] }
    const h = hashOf({ agg: 'wroclaw', layers: ['x'] }, d)
    expect(readHash(h)).toMatchObject({ agg: 'wroclaw', layers: ['x'], variants: {} })
  })
  it('drops unknown agglomerations and not-ready layers', () => {
    const r = resolveHash({ agg: 'nope', layers: ['d', 'x', 'zzz'] }, catalog)
    expect(r.agg).toBeNull()
    expect([...activeIds(r.state, catalog.layers)]).toEqual([])   // x is of an unlisted kind here, d is not ready
    const def = resolveHash({}, catalog)
    expect(def.agg).toBeNull()
    expect([...activeIds(def.state, catalog.layers)]).toEqual(['fua'])
  })
})

describe('ramp', () => {
  const ramp = { stops: [0, 1000, 3000], colors: ['#a', '#b', '#c'] }
  it('builds classes with open ends', () => {
    expect(rampClasses(ramp)).toEqual([
      { color: '#a', from: null, to: 1000 },
      { color: '#b', from: 1000, to: 3000 },
      { color: '#c', from: 3000, to: null },
    ])
  })
  it('accepts one colour more than stops', () => {
    const c = rampClasses({ stops: [10, 20], colors: ['#0', '#1', '#2'] })
    expect(c.map((x) => [x.from, x.to])).toEqual([[null, 10], [10, 20], [20, null]])
  })
  it('makes a step expression that guards no data', () => {
    const e = rampExpression('d', ramp)
    expect(e[0]).toBe('case')
    expect(e[1]).toEqual(['==', ['typeof', ['get', 'd']], 'number'])
    expect(e[2]).toEqual(['step', ['get', 'd'], '#a', 1000, '#b', 3000, '#c'])
    expect(e[3]).toBe('rgba(0,0,0,0)')
  })
  it('labels classes', () => {
    expect(flat(classLabel({ from: 1000, to: 3000 }))).toBe('1 000\u20133 000')
    expect(flat(classLabel({ from: 20000, to: null }, 'os./km²'))).toBe('od 20 000 os./km²')
    expect(flat(classLabel({ from: null, to: 1000 }))).toBe('poniżej 1 000')
  })
})

describe('metrics', () => {
  const rows = [
    { agglomeration: 'a', domain: 'core', label: 'x', value: 1, unit: '%' },
    { agglomeration: 'a', domain: 'fua', label: 'y', value: 4321, unit: 'os./km²' },
    { agglomeration: 'b', domain: 'fua', label: 'z', value: 0, unit: '' },
    { agglomeration: 'a', domain: 'zzz', label: 'w', value: null },
  ]
  it('groups by domain, FUA first, for one agglomeration', () => {
    const g = groupMetrics(rows, 'a')
    expect(g.map((x) => x.domain)).toEqual(['fua', 'core', 'zzz'])
    expect(groupMetrics(rows, 'b')).toHaveLength(1)
    expect(groupMetrics(undefined, 'a')).toEqual([])
  })
  it('supports three domains in order, keeps file order, drops qa rows', () => {
    const r = [
      { agglomeration: 'a', domain: 'covered', label: 'c1', value: 1 },
      { agglomeration: 'a', domain: 'core', label: 'k2', value: 2, tier: 'table' },
      { agglomeration: 'a', domain: 'fua', label: 'f2', value: 3, tier: 'table' },
      { agglomeration: 'a', domain: 'fua', label: 'f1', value: 4, tier: 'main' },
      { agglomeration: 'a', domain: 'core', label: 'k1', value: 5, tier: 'main' },
      { agglomeration: 'a', domain: 'covered', label: 'qa', value: 6, tier: 'qa' },
      { agglomeration: 'a', domain: 'covered', label: 'c2', value: null },
    ]
    const g = groupMetrics(r, 'a')
    expect(g.map((x) => x.domain)).toEqual(['fua', 'core', 'covered'])
    expect(g.map((x) => x.title)).toEqual(['Cały obszar FUA', 'Rdzeń miasta', 'Obszar pokryty danymi o rozkładach'])
    expect(g[0].rows.map((x) => x.label)).toEqual(['f2', 'f1'])
    expect(g[1].rows.map((x) => x.label)).toEqual(['k2', 'k1'])
    expect(g[2].rows.map((x) => x.label)).toEqual(['c1', 'c2'])
    expect(g[2].rows[1].value).toBeNull()
  })
  it('places the urban centre after the covered area, before the tram network, with a Polish heading', () => {
    const r = [
      { agglomeration: 'a', domain: 'city_tram_network', label: 't', value: 1 },
      { agglomeration: 'a', domain: 'urban_centre', label: 'u', value: 2, tier: 'main' },
      { agglomeration: 'a', domain: 'covered', label: 'c', value: 3 },
      { agglomeration: 'a', domain: 'core', label: 'k', value: 4 },
    ]
    const g = groupMetrics(r, 'a')
    expect(g.map((x) => x.domain)).toEqual(['core', 'covered', 'urban_centre', 'city_tram_network'])
    expect(g[2].title).toBe('Centrum miejskie (urban centre, Eurostat 2021)')
  })
  it('formats percentages with one decimal and a comma', () => {
    expect(flat(formatValue({ value: 80.38, unit: '%' }).text)).toBe('80,4 %')
    expect(flat(formatValue({ value: 5, unit: '%' }).text)).toBe('5,0 %')
    expect(formatValue({ value: null, unit: '%' })).toEqual({ text: NO_DATA, missing: true })
  })
  it('names the feed variant and population grid in the small print', () => {
    const all = metricNotes({ feed_variant: 'all', population_grid: 'ghsl_census_scaled', grid: 'tech' })
    expect(flat(all)).toBe('GHSL 250 m przeskalowany do spisu 1 km \u00b7 wszystkie feedy, w tym nieoficjalne')
    expect(flat(metricNotes({ feed_variant: 'official', population_grid: 'ghsl_raw' })))
      .toBe('GHSL 250 m \u00b7 feedy oficjalne')
    expect(metricNotes({ grid: '1 km' })).toBe('1 km')
  })
  it('formats values; null is "brak danych", zero stays zero', () => {
    expect(flat(formatValue(rows[1]).text)).toBe('4 321 os./km²')
    expect(formatValue(rows[3])).toEqual({ text: NO_DATA, missing: true })
    expect(formatValue(rows[2])).toEqual({ text: '0', missing: false })
    expect(NO_DATA).toBe('brak danych')
  })
  it('writes the small print', () => {
    const s = metricNotes({ grid: '1 km', source: 'GUS', population_date: '2021', timetable_date: '2026-11-02', coverage_share: 0.5 })
    expect(flat(s)).toBe('1 km \u00b7 GUS \u00b7 ludność: 2021 \u00b7 rozkłady: 2026-11-02 \u00b7 pokrycie danymi: 50 %')
  })
})

describe('urls', () => {
  it('maps catalog paths onto the configured bases', () => {
    expect(resolveUrl('data/fua.geojson')).toBe('./data/fua.geojson')
    expect(resolveUrl('tiles/a.pmtiles', './data/', 'https://cdn.example/t/')).toBe('https://cdn.example/t/a.pmtiles')
    expect(resolveUrl('https://x/y')).toBe('https://x/y')
    expect(absoluteUrl('data/fua.geojson', 'https://h/site/')).toBe('https://h/site/data/fua.geojson')
  })
})

describe('map layers', () => {
  it('draws a choropleth with a hatched no-data layer', () => {
    const l = { id: 'd', type: 'pmtiles', url: 'tiles/d.pmtiles', source_layer: 'dd', property: 'v', kind: 'choropleth', ramp: { stops: [0, 1], colors: ['#a', '#b'] } }
    const s = layerSpecs(l)
    expect(s.map((x) => x.id)).toEqual(['d:fill', 'd:nodata'])
    expect(s.every((x) => x['source-layer'] === 'dd')).toBe(true)
    expect(s[1].paint['fill-pattern']).toBe('hatch')
    expect(sourceSpec(l, ).url.startsWith('pmtiles://')).toBe(true)
  })
  it('geojson boundary has no source-layer', () => {
    const s = layerSpecs({ id: 'fua', type: 'geojson', url: 'data/fua.geojson', kind: 'boundary' }, 'lodz')
    expect(s.some((x) => 'source-layer' in x)).toBe(false)
    expect(s.map((x) => x.id)).toContain('fua:sel')
  })
  it('hatch image has opaque stripes and a see-through ground', () => {
    const h = hatchImage(12)
    expect(h.data.length).toBe(12 * 12 * 4)
    expect(new Set(Array.from({ length: 144 }, (_, i) => h.data[i * 4 + 3])).size).toBe(2)
  })
})

describe('legend', () => {
  const ramp = { stops: [10, 20], colors: ['#0', '#1', '#2'] }
  it('derives class labels from the bounds', () => {
    expect(rampLegend(ramp).map((r) => flat(r.label))).toEqual(['poniżej 10', '10–20', 'od 20'])
    expect(rampLegend(ramp).map((r) => r.color)).toEqual(['#0', '#1', '#2'])
  })
  it('uses the labels of a ramp when there is one per colour', () => {
    const labels = ['co ≤ 5 min', 'co ≤ 10 min', 'rzadziej']
    expect(rampLegend({ ...ramp, labels }).map((r) => r.label)).toEqual(labels)
    // a wrong count is ignored rather than shown misaligned
    expect(rampLegend({ ...ramp, labels: ['a'] }).map((r) => flat(r.label))).toEqual(['poniżej 10', '10–20', 'od 20'])
  })
  it('shows the hatched row only for layers that can have no-data cells', () => {
    const l = { kind: 'choropleth', ramp }
    expect(legendRows(l).noData).toBeNull()
    expect(legendRows({ ...l, has_nodata: true }).noData).toBe('brak danych o rozkładach')
    expect(legendRows({ ...l, has_nodata: true, nodata_label: 'x' }).noData).toBe('x')
    expect(legendRows({ kind: 'mask' })).toEqual({ rows: [], noData: null })
  })
})

describe('the sort of the comparison in the address', () => {
  const d = { layers: ['fua'] }
  const catalog = { agglomerations: [{ id: 'wroclaw' }], layers: [{ id: 'fua', kind: 'boundary', status: 'ready' }] }
  it('is written after the rest, only when there is one, and read back', () => {
    const h = hashOf({ agg: 'lodz', layers: ['x', 'fua'], sort: { key: 'pwdens_census_1km', dir: 'desc' } }, d)
    expect(h).toBe('#a=lodz&l=fua,x&s=pwdens_census_1km:desc')
    const r = readHash(h)
    expect(r.sort).toEqual({ key: 'pwdens_census_1km', dir: 'desc' })
    expect(r.agg).toBe('lodz')
    expect(hashOf({ agg: null, layers: ['fua'], sort: null }, d)).toBe('')
    expect(hashOf({ agg: null, layers: ['fua'], sort: { key: 'area', dir: 'desc' } }, d)).toBe('#s=area:desc')
  })
  it('leaves old addresses as they were: no sort, and the same hash back', () => {
    const r = readHash('#a=wroclaw&l=fua,x&v=d:2')
    expect(r.sort).toBeUndefined()
    expect(resolveHash(r, catalog).sort).toBeNull()
    // the second sort of the older two-table page is simply ignored
    expect(readHash('#sd=area:asc').sort).toBeUndefined()
    expect(hashOf({ agg: 'wroclaw', layers: ['x', 'fua'], variants: r.variants }, d)).toBe('#a=wroclaw&l=fua,x&v=d:2')
  })
  it('drops what is not a sort: no way, a wrong way, no metric', () => {
    expect(readHash('#s=area').sort).toBeUndefined()
    expect(readHash('#s=area:up').sort).toBeUndefined()
    expect(readHash('#s=:asc').sort).toBeUndefined()
    expect(readHash('#s=').sort).toBeUndefined()
    expect(hashOf({ agg: null, layers: ['fua'], sort: { key: 'area', dir: 'sideways' } }, d)).toBe('')
  })
  it('resolves to null for no sort and to the sort for a sort, keeping the rest of the state', () => {
    const r = resolveHash(readHash('#a=nope&s=area:desc&sd=rho_t20:asc'), catalog)
    expect(r.sort).toEqual({ key: 'area', dir: 'desc' })
    expect(r.agg).toBeNull()
  })
})
