import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { DataTable } from '@bartor-net/ui-kit'
import Compare from './Compare'
import CityPanel from './CityPanel'
import { cityGroups } from './tableModel'
import Sidebar from './Sidebar'
import { indexMetrics, topNodes } from './metricTable'
import { initialState, setOverlayOn, setValue } from './layerControl'

const html = (el) => renderToStaticMarkup(el)
const noop = () => {}

describe('the kit table, as this app feeds it', () => {
  const columns = [{ key: 'a', head: 'A', title: 'Aaa', onPick: noop }, { key: 'b', head: 'B', help: h('p', null, 'o kolumnie') }]
  const groups = [{
    id: 'g', title: 'Grupa',
    rows: [
      { id: 'r1', label: 'Wiersz', unit: '%', help: h('p', null, 'wyjaśnienie'), actions: [{ label: 'na mapie', onClick: noop }],
        cells: [{ content: '1', tone: 'best' }, { content: '–', tone: 'dim' }] },
      { id: 'r2', label: 'Bez pomocy', cells: [{ content: '2' }] },
    ],
  }]
  it('has a "?" with aria-expanded only on rows and columns that have help, and no help text until opened', () => {
    const s = html(h(DataTable, { columns, groups, hot: 'a', caption: 'Tabela' }))
    expect((s.match(/aria-expanded="false"/g) || []).length).toBe(2)
    expect(s).not.toContain('wyjaśnienie')
    expect(s).toContain('na mapie')
    expect(s).toContain('kit-data-best')
    expect(s).toContain('kit-data-col hot')
    expect(s).toContain('role="region"')
    // a missing cell is a dash, never empty
    expect(s).toContain('Bez pomocy')
  })
})

const L = (id, kind, extra = {}) => ({ id, kind, status: 'ready', title: id, ...extra })
const catalog = {
  generated: '2026-11-24',
  agglomerations: [{ id: 'lodz', name: 'Łódź', phase: 1, note: 'Uwaga.' }, { id: 'krakow', name: 'Kraków', phase: 1 }, { id: 'kielce', name: 'Kielce' }],
  layers: [
    L('fua', 'boundary', { title: 'Granice' }), L('d', 'choropleth', { title: 'Gęstość', unit: 'os./km²', ramp: { stops: [1], colors: ['#a', '#b'] }, note: 'Nota.' }),
    L('m', 'mask', { title: 'Brak danych' }),
    L('p', 'points', { title: 'Węzły: dojście', ramp: { stops: [1], colors: ['#a', '#b'] } }), L('q', 'points', { title: 'Węzły: czekanie', ramp: { stops: [1], colors: ['#a', '#b'] } }),
    L('weird', 'heatmap', { title: 'Nieznana' }),
  ],
}
const row = (agglomeration, metric, domain, value, extra = {}) => ({ agglomeration, metric, domain, value, unit: '%', label: `L ${metric}`, tier: 'main', ...extra })
const cities = ['warszawa', 'krakow', 'lodz']
const metrics = [
  ...cities.map((c, i) => row(c, 'tp_pt_am_30min', 'core', 20 + i, { source: 'R5', flag: c === 'lodz' ? 'uwaga' : null })),
  ...cities.map((c, i) => row(c, 'pwdens_census_1km', 'core', 5000 + i, { unit: 'os./km²' })),
  row('lodz', 'unknown_metric', 'core', null, { label: 'Nowa miara' }),
]
const index = indexMetrics(metrics)

describe('panels render without a browser', () => {
  const all = [...cities, 'kielce']
  const cmp = (extra = {}) => ({
    index, cities, everyCity: all, names: { lodz: 'Łódź', kielce: 'Kielce' }, area: 'core', layers: catalog.layers,
    onShowLayer: noop, onPickCity: noop, hot: 'lodz', setHot: noop, onOpenLimits: noop, layout: 'tabs', ...extra,
  })
  it('the comparison is one table of all agglomerations: group captions, a dash for the city without timetables, no area chips', () => {
    const s = html(h(Compare, cmp()))
    expect(s).toContain('Zasięg komunikacją w 30 min')
    expect(s).toContain('Nowa miara')
    expect(s).toContain('z danymi o transporcie')           // caption of the first group
    expect(s).toContain('tylko gęstość i forma')            // caption of the second
    expect(s).toContain('brak danych o rozkładach jazdy')   // the cell of Kielce on a transport measure
    expect(s).toContain('a nie zero')
    expect(s).toContain('kit-data-col hot')
    expect(s).not.toContain('kit-chip')                      // the area is the global switch in the header
    expect(s).not.toContain('Gęstość: wszystkie')            // the second table is gone
    expect(s.includes('>na mapie<')).toBe(false)         // layers of these metrics are not in this catalog
    const withLayer = html(h(Compare, cmp({ layers: [L('density_250m', 'choropleth')] })))
    expect(withLayer).toContain('>na mapie<')
  })
  it('says in the row when a measure is read in another area than the chosen one', () => {
    const idx = indexMetrics([...metrics, ...cities.map((c, i) => row(c, 'only_fua', 'fua', 3 + i))])
    const s = html(h(Compare, cmp({ index: idx })))
    expect(s).toContain('obszar: Cały obszar')
    expect(s).toContain('najbliższego obszaru')
  })
  it('the tabs of the comparison hold either the table or the charts', () => {
    const miary = html(h(Compare, cmp({ tab: 'miary', spread: h('i', { className: 'spread' }) })))
    expect(miary).not.toContain('class="spread"')
    const wykresy = html(h(Compare, cmp({ tab: 'wykresy', spread: h('i', { className: 'spread' }), chart: h('i', { className: 'bars' }) })))
    expect(wykresy).toContain('class="spread"')
    expect(wykresy).toContain('class="bars"')
    expect(wykresy).not.toContain('kit-data-table')
  })
  describe('sorting the comparison by a row', () => {
    const more = indexMetrics([
      ...metrics,
      ...[['warszawa', 3, 900], ['krakow', 1, 1200], ['lodz', 2, null]].flatMap(([c, rho, area]) => [
        row(c, 'rho_t20', 'core', rho, { unit: '' }), row(c, 'area', 'core', area, { unit: 'km²' }),
      ]),
    ])
    const base = cmp({ index: more, everyCity: cities, hot: null, names: {} })
    const heads = (s) => [...s.matchAll(/kit-data-pick">([^<]+)</g)].map((m) => m[1]).slice(0, 3)
    it('keeps the default order of the cities without a sort', () => {
      const s = html(h(Compare, base))
      expect(heads(s)).toEqual(['Warszawa', 'Kraków', 'Łódź'])
      expect(s).not.toContain('Domyślna kolejność')
      expect(s).not.toContain('aria-sort')
    })
    it('puts the best first: high first where higher is better, low first where lower is', () => {
      expect(heads(html(h(Compare, { ...base, sort: { key: 'pwdens_census_1km', dir: 'desc' } })))).toEqual(['Łódź', 'Kraków', 'Warszawa'])
      const lower = html(h(Compare, { ...base, sort: { key: 'rho_t20', dir: 'asc' } }))
      expect(heads(lower)).toEqual(['Kraków', 'Łódź', 'Warszawa'])
      expect(lower).toContain('najlepsze pierwsze')
      expect(lower).toContain('Domyślna kolejność')
      expect(lower).toContain('aria-sort="ascending"')
    })
    it('puts a city without a number last, whichever way, and does not call a metric without a direction best', () => {
      for (const dir of ['asc', 'desc']) {
        const s = html(h(Compare, { ...base, sort: { key: 'area', dir } }))
        expect(heads(s)[2]).toBe('Łódź')
        expect(s).not.toContain('najlepsze pierwsze')
      }
      expect(heads(html(h(Compare, { ...base, sort: { key: 'area', dir: 'desc' } })))).toEqual(['Kraków', 'Warszawa', 'Łódź'])
    })
    it('ignores a sort of a metric the table does not have, as an old link might carry', () => {
      const s = html(h(Compare, { ...base, sort: { key: 'nie_ma_takiej', dir: 'desc' } }))
      expect(heads(s)).toEqual(['Warszawa', 'Kraków', 'Łódź'])
      expect(s).not.toContain('Domyślna kolejność')
    })
    it('drops the group captions while the cities are sorted (a mixed order cannot keep them)', () => {
      const mixed = cmp({ index: more, everyCity: [...cities, 'kielce'] })
      expect(html(h(Compare, mixed))).toContain('tylko gęstość i forma')
      expect(html(h(Compare, { ...mixed, sort: { key: 'pwdens_census_1km', dir: 'desc' } }))).not.toContain('tylko gęstość i forma')
    })
  })
  it('the comparison says so when there are no metrics', () => {
    const s = html(h(Compare, cmp({ index: {}, cities: [], everyCity: [], names: {} })))
    expect(s).toContain('po przeliczeniu')
  })
  describe('the city view and its tabs', () => {
    const feats = [{ geometry: { type: 'Point', coordinates: [1, 2] }, properties: { agg: 'lodz', id: 'n1', name: 'DWORZEC GŁÓWNY', dep_h: 50, walk_dir: 1, wait_am: 2 } }]
    const nodes = { layer: catalog.layers[3], nodes: topNodes(feats, 'lodz') }
    const base = {
      agglomeration: catalog.agglomerations[0], index, pool: [...cities, 'kielce'], transport: cities, layers: catalog.layers, area: 'core',
      onShowLayer: noop, onClose: noop, onBack: noop, onPickNode: noop, setTab: noop, nodes,
    }
    it('"Najważniejsze" has the headline numbers with their rank, the note, tabs, and no stage badge', () => {
      const s = html(h(CityPanel, { ...base, tab: 'najwazniejsze' }))
      expect(s).toContain('Łódź')
      expect(s).toContain('Najważniejsze liczby')
      expect(s).toContain('1. z 3')                    // rank among the cities that have the measure, never 8/7
      expect(s).toContain('Uwaga.')
      expect(s).toContain('role="tablist"')
      expect(s).toContain('aria-selected="true"')
      expect(s).not.toContain('Etap')
    })
    it('"Wszystkie miary" has one value column for the area and the rank; "Przesiadki" has the stop areas in title case', () => {
      const s = html(h(CityPanel, { ...base, tab: 'miary' }))
      expect(s).toContain('Miasto')
      expect(s).not.toContain('Centrum miejskie')       // one column: the other areas are on the metric page
      expect(s).toContain('1/3')
      const stops = html(h(CityPanel, { ...base, tab: 'przesiadki' }))
      expect(stops).toContain('Najruchliwsze zespoły przystanków')
      expect(stops).toContain('Dworzec Główny')
      expect(stops).toContain('dojście 1 min, czekanie 2 min')
      expect(html(h(CityPanel, { ...base, tab: 'przesiadki', nodes: null }))).not.toContain('Najruchliwsze')
    })
    it('a city without metrics says so', () => {
      const s = html(h(CityPanel, { ...base, agglomeration: catalog.agglomerations[2], layers: [], nodes: null, tab: 'miary' }))
      expect(s).toContain('nie ma jeszcze przeliczonych miar')
    })
    it('a rank is blank for a measure without a direction and n is how many cities have it', () => {
      const idx = indexMetrics([
        ...['a', 'b', 'c', 'd'].map((c, i) => row(c, 'area', 'core', 100 + i, { unit: 'km²' })),
        ...['a', 'b', 'c'].map((c, i) => row(c, 'pwdens_census_1km', 'core', 5000 + i, { unit: 'os./km²' })),
      ])
      const groups = cityGroups({ index: idx, pool: ['a', 'b', 'c', 'd', 'e'], agg: 'a', area: 'core', layers: [], onShowLayer: noop })
      const cellOf = (id) => groups.flatMap((g) => g.rows).find((r) => r.id === id).cells[1]
      expect(cellOf('area').content).toBe('')
      expect(cellOf('pwdens_census_1km').content).toBe('3/3')
    })
  })
  it('the sidebar is only the map: radio cards for value layers and, under "Więcej na mapie", the overlays', () => {
    const view = setOverlayOn(setValue(initialState(catalog.layers), 'd', catalog.layers), 'points', true)
    const props = {
      catalog, view, onValue: noop, onOverlayOn: noop, onOverlayLayer: noop, onVariant: noop, sheetOpen: false, setSheetOpen: noop, onAbout: noop,
    }
    const s = html(h(Sidebar, props))
    expect(s).toContain('Bez warstwy (tylko granice)')
    expect((s.match(/type="radio"/g) || []).length).toBe(2)       // "Bez warstwy" and the one value layer
    expect(s).toContain('Więcej na mapie')
    expect((s.match(/kit-switch/g) || []).length).toBe(2)         // outlines and nodes; the hatch is not a switch
    expect(s).not.toContain('kit-check')                          // nothing that looks like a checkbox
    expect(s).toContain('Węzły przesiadkowe')
    expect(s).toContain('czekanie')                               // chooser of the points layer
    expect(s).not.toContain('Nieznana')
    // no city picker, no comparison link, no legend, no layer note in the open (it is behind the "?")
    expect(s).not.toContain('Porównanie')
    expect(s).not.toContain('<select')
    expect(s).not.toContain('legend-row')
    expect(s).not.toContain('Nota.')
    expect(s).toContain('aria-expanded="false"')
    const collapsed = html(h(Sidebar, { ...props, collapsed: true }))
    expect(collapsed).toContain('Gęstość')                          // only the active layer's name
    expect(collapsed).not.toContain('type="radio"')
  })
})
