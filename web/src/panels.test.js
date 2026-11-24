import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import ExpandTable from './kitx/ExpandTable'
import Compare from './Compare'
import CityPanel from './CityPanel'
import Sidebar from './Sidebar'
import { indexMetrics, topNodes } from './metricTable'
import { initialState, setOverlayOn, setValue, activeIds } from './layerControl'
import { EMPTY_FOCUSES } from './classFocus'

const html = (el) => renderToStaticMarkup(el)
const noop = () => {}

describe('ExpandTable (kitx)', () => {
  const columns = [{ key: 'a', head: 'A', title: 'Aaa', onPick: noop }, { key: 'b', head: 'B', help: h('p', null, 'o kolumnie') }]
  const groups = [{
    id: 'g', title: 'Grupa',
    rows: [
      { id: 'r1', label: 'Wiersz', unit: '%', help: h('p', null, 'wyjaśnienie'), action: { label: 'na mapie', onClick: noop },
        cells: [{ text: '1', tone: 'best' }, { text: '–', tone: 'dim' }] },
      { id: 'r2', label: 'Bez pomocy', cells: [{ text: '2' }] },
    ],
  }]
  it('has a "?" with aria-expanded only on rows and columns that have help, and no help text until opened', () => {
    const s = html(h(ExpandTable, { columns, groups, hot: 'a', caption: 'Tabela' }))
    expect((s.match(/aria-expanded="false"/g) || []).length).toBe(2)
    expect(s).not.toContain('wyjaśnienie')
    expect(s).toContain('na mapie')
    expect(s).toContain('kitx-best')
    expect(s).toContain('kitx-col hot')
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
    L('weird', 'lines', { title: 'Nieznana' }),
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
  it('the comparison has area chips, a table, the density table and the reminder; the "na mapie" link only for existing layers', () => {
    const s = html(h(Compare, {
      index, cities, everyCity: [...cities, 'kielce'], names: { lodz: 'Łódź' }, area: 'core', setArea: noop, layers: catalog.layers,
      onShowLayer: noop, onPickCity: noop, hot: 'lodz', setHot: noop, onOpenLimits: noop,
    }))
    expect(s).toContain('Centrum miejskie')
    expect(s).toContain('Zasięg komunikacją w 30 min')
    expect(s).toContain('Gęstość: wszystkie 4 miast')
    expect(s).toContain('a nie zero')
    expect(s).toContain('Nowa miara')
    expect(s).toContain('kitx-col hot')
    expect(s.includes('na mapie')).toBe(false)   // layers of these metrics are not in this catalog
    const withLayer = html(h(Compare, {
      index, cities, everyCity: cities, names: {}, area: 'core', setArea: noop,
      layers: [L('density_250m', 'choropleth')], onShowLayer: noop, onPickCity: noop, hot: null, setHot: noop, onOpenLimits: noop,
    }))
    expect(withLayer).toContain('na mapie')
  })
  it('the comparison says so when there are no metrics', () => {
    const s = html(h(Compare, {
      index: {}, cities: [], everyCity: [], names: {}, area: 'core', setArea: noop, layers: [], onShowLayer: noop,
      onPickCity: noop, hot: null, setHot: noop, onOpenLimits: noop,
    }))
    expect(s).toContain('po przeliczeniu')
  })
  it('a city panel shows rank, areas, the nodes block only when it has nodes, and the note', () => {
    const feats = [{ geometry: { type: 'Point', coordinates: [1, 2] }, properties: { agg: 'lodz', id: 'n1', name: 'Dworzec', dep_h: 50, walk_dir: 1, wait_am: 2 } }]
    const nodes = { layer: catalog.layers[3], nodes: topNodes(feats, 'lodz') }
    const base = { agglomeration: catalog.agglomerations[0], index, cities, layers: catalog.layers, onShowLayer: noop, onClose: noop, onPickNode: noop }
    const s = html(h(CityPanel, { ...base, nodes }))
    expect(s).toContain('Łódź')
    expect(s).toContain('1/3')   // rank among the three cities with data
    expect(s).toContain('Centrum miejskie')
    expect(s).toContain('W środku aglomeracji')
    expect(s).toContain('Dworzec')
    expect(s).toContain('dojście 1 min, czekanie 2 min')
    expect(s).toContain('Uwaga.')
    const bare = html(h(CityPanel, { ...base, nodes: null }))
    expect(bare).not.toContain('W środku aglomeracji')
    expect(bare).not.toContain('Najruchliwsze')
  })
  it('a city without metrics says so', () => {
    const s = html(h(CityPanel, {
      agglomeration: catalog.agglomerations[2], index, cities, layers: [], onShowLayer: noop, onClose: noop, nodes: null, onPickNode: noop,
    }))
    expect(s).toContain('nie ma jeszcze przeliczonych miar')
  })
  it('the sidebar has radio cards for value layers, switches for overlays, a chooser for two points layers, and ignores unknown kinds', () => {
    let view = setOverlayOn(setValue(initialState(catalog.layers), 'd', catalog.layers), 'points', true)
    const props = {
      catalog, metrics: { generated: 'x', metrics }, selectedId: null, onPick: noop, view, active: activeIds(view, catalog.layers),
      onValue: noop, onOverlayOn: noop, onOverlayLayer: noop, onVariant: noop,
      focus: { focuses: EMPTY_FOCUSES, onHover: noop, onToggle: noop, onClear: noop },
      sheetOpen: false, setSheetOpen: noop, onAbout: noop, onCompare: noop, sharesOf: () => undefined,
    }
    const s = html(h(Sidebar, props))
    expect(s).toContain('Tylko granice')
    expect((s.match(/type="radio"/g) || []).length).toBe(2)       // "Tylko granice" and the one value layer
    expect((s.match(/kit-switch/g) || []).length).toBe(3)         // outlines, no-data hatch, nodes
    expect(s).not.toContain('kit-check')                          // nothing that looks like a checkbox
    expect(s).toContain('Węzły przesiadkowe')
    expect(s).toContain('czekanie')                               // chooser of the points layer
    expect(s).toContain('Porównanie miast')
    expect(s).not.toContain('Nieznana')
    const withShares = html(h(Sidebar, { ...props, sharesOf: (id) => (id === 'd' ? [0.3, 0.7] : undefined) }))
    expect(withShares).toContain('30 %')
    expect(s).not.toContain('legend-share')
  })
})
