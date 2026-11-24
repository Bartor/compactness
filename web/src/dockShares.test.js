import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import {
  layerAggs, pickedSum, scopeData, scopeLabel, shareFractions, shareText,
} from './classShares'
import { focusPick, pinnedOf } from './classPick'
import { EMPTY_FOCUS, hoverClass, togglePinned } from './classFocus'
import { outsideMask, WORLD_RING } from './outsideMask'
import {
  DOCK_STATES, FOLDED_PX, dockHeight, parseDock, refitOnChange, snapDock, stepDock,
} from './kitx/dock'
import { hashOf, hashOfView, readHash, resolveHash } from './urlState'
import { initialState } from './layerControl'
import { syncOutside, syncOverlays, OUTSIDE_LAYER, OUTSIDE_SOURCE } from './mapLayers'
import { CitiesClassBars, CityClassChart } from './ClassChart'
import Legend from './Legend'
import DockStage from './kitx/DockStage'
import MapLegendBox from './kitx/MapLegendBox'

const doc = {
  layers: {
    L: {
      all: { fua: { pop: [60, 40], cells: [6, 4], nodata_pop: 100, nodata_cells: 10 }, core: { pop: [30, 20], cells: [3, 2], nodata_pop: null, nodata_cells: null } },
      a: { fua: { pop: [10, 30], cells: [1, 3], nodata_pop: 60, nodata_cells: 6 }, core: { pop: [0, 0], cells: [0, 0], nodata_pop: null, nodata_cells: null } },
      b: { fua: { pop: [50, 10], cells: [5, 1], nodata_pop: 40, nodata_cells: 4 }, core: { pop: [30, 20], cells: [3, 2], nodata_pop: null, nodata_cells: null } },
    },
  },
}
const layer = {
  id: 'L', kind: 'choropleth', title: 'Warstwa', unit: 'jedn.', has_nodata: true, nodata_label: 'brak danych X',
  ramp: { stops: [1], colors: ['#111111', '#eeeeee'], labels: ['mało', 'dużo'] },
}

describe('shares of a scope', () => {
  it('takes one agglomeration or, with none, the whole coverage, in the whole area or the core', () => {
    expect(scopeData(doc, 'L', 'a', 'fua')).toMatchObject({ agg: 'a', pop: [10, 30], nodataPop: 60, totalPop: 100, totalCells: 10 })
    expect(scopeData(doc, 'L', null, 'core')).toMatchObject({ agg: 'all', pop: [30, 20], nodataPop: null, totalPop: 50, totalCells: 5 })
    expect(scopeData(doc, 'L', null)).toMatchObject({ agg: 'all', area: 'fua', totalPop: 200, totalCells: 20 })
  })
  it('has nothing for a layer or city the file does not know, or for no file', () => {
    expect(scopeData(doc, 'L', 'zzz')).toBeNull()
    expect(scopeData(doc, 'nope', null)).toBeNull()
    expect(scopeData({}, 'L', null)).toBeNull()
    expect(scopeData(null, 'L', null)).toBeNull()
    expect(scopeData(doc, 'L', 'a', 'core')).toBeNull()   // no cells at all in that area
  })
  it('shares of residents and of cells add up to one with no data included', () => {
    const f = shareFractions(scopeData(doc, 'L', 'a'))
    expect(f.pop).toEqual([0.1, 0.3])
    expect(f.nodataPop).toBeCloseTo(0.6)
    expect(f.pop.reduce((x, y) => x + y, 0) + f.nodataPop).toBeCloseTo(1)
    expect(f.cells[1]).toBeCloseTo(0.3)
    expect(shareFractions(null)).toBeNull()
    expect(shareFractions(scopeData(doc, 'L', null, 'core')).nodataPop).toBeNull()
  })
  it('adds up the picked classes: shares of residents and of cells', () => {
    const s = scopeData(doc, 'L', 'b')
    expect(pickedSum(s, [0])).toMatchObject({ pop: 50, cells: 5, popShare: 0.5, cellShare: 0.5 })
    expect(pickedSum(s, [0, 1, 1])).toMatchObject({ pop: 60, cells: 6 })
    expect(pickedSum(s, [])).toMatchObject({ pop: 0, popShare: 0 })
    expect(pickedSum(s, [7, -1])).toMatchObject({ pop: 0 })
  })
  it('names the scope and writes shares as whole percentages', () => {
    expect(scopeLabel('Wrocław', 'core')).toBe('Wrocław, miasto')
    expect(scopeLabel(null)).toBe('wszystkie miasta z tą warstwą, cały obszar')
    expect(shareText([0.234, 0.004, 0.762], 0)).toBe('23 %')
    expect(shareText([0.234, 0.004], 1)).toBe('<1 %')
    expect(shareText([0.5], 3)).toBe('')
    expect(shareText(undefined, 0)).toBe('')
    expect(layerAggs(doc, 'L')).toEqual(['a', 'b'])
  })
})

describe('class focus as the kit pick', () => {
  const calls = []
  const handlers = { onHover: (...a) => calls.push(['hover', ...a]), onToggle: (...a) => calls.push(['toggle', ...a]) }
  it('lights what the legend lights and pins what it pins', () => {
    let f = togglePinned(EMPTY_FOCUS, 'L', 1)
    f = hoverClass(f, 'L', 0)
    const p = focusPick(f, 'L', handlers)
    expect([...p.active].sort()).toEqual(['0', '1'])
    expect([...p.pinned]).toEqual(['1'])
    expect(pinnedOf(f, 'L')).toEqual([1])
    expect(pinnedOf(f, 'other')).toEqual([])
  })
  it('hovering and clicking a slice or row do what they do in the legend', () => {
    calls.length = 0
    const p = focusPick(EMPTY_FOCUS, 'L', handlers)
    const on = p.on('1')
    on.onMouseEnter(); on.onMouseLeave(); on.onClick()
    expect(calls).toEqual([['hover', 'L', 1], ['hover', 'L', null], ['toggle', 'L', 1]])
  })
  it('ignores keys that are not classes, and does not preview on a screen without hover', () => {
    calls.length = 0
    const p = focusPick(EMPTY_FOCUS, 'L', handlers, false)
    expect(p.on('nodata')).toEqual({})
    p.toggle('nodata')
    expect(p.on('0').onMouseEnter).toBeUndefined()
    expect(calls).toEqual([])
  })
  it('a pinned class of another layer lights nothing here', () => {
    expect(focusPick(togglePinned(EMPTY_FOCUS, 'X', 0), 'L', handlers).active.size).toBe(0)
  })
})

describe('the veil outside a city', () => {
  const sq = (x, y, s) => [[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]]
  const f = (id, level, geometry) => ({ type: 'Feature', properties: { id, level }, geometry })
  it('is the world with the area of the city cut out, ignoring the core and other cities', () => {
    const feats = [
      f('a', 'fua', { type: 'Polygon', coordinates: [sq(10, 50, 2)] }),
      f('a', 'core', { type: 'Polygon', coordinates: [sq(10.5, 50.5, 1)] }),
      f('b', 'fua', { type: 'Polygon', coordinates: [sq(20, 50, 2)] }),
    ]
    const m = outsideMask(feats, 'a')
    expect(m.geometry.type).toBe('Polygon')
    expect(m.geometry.coordinates).toEqual([WORLD_RING, sq(10, 50, 2)])
  })
  it('cuts out every part of a multipolygon and fills the holes of the area again', () => {
    const hole = sq(10.5, 50.5, 0.5)
    const feats = [f('a', 'fua', { type: 'MultiPolygon', coordinates: [[sq(10, 50, 2), hole], [sq(30, 50, 1)]] })]
    const m = outsideMask(feats, 'a')
    expect(m.geometry.type).toBe('MultiPolygon')
    expect(m.geometry.coordinates[0]).toEqual([WORLD_RING, sq(10, 50, 2), sq(30, 50, 1)])
    expect(m.geometry.coordinates[1]).toEqual([hole])
  })
  it('is null for no city, an unknown city or no data', () => {
    expect(outsideMask([], 'a')).toBeNull()
    expect(outsideMask(null, 'a')).toBeNull()
    expect(outsideMask([f('a', 'core', { type: 'Polygon', coordinates: [sq(0, 0, 1)] })], 'a')).toBeNull()
    expect(outsideMask([f('a', 'fua', { type: 'Polygon', coordinates: [sq(0, 0, 1)] })], null)).toBeNull()
  })
  it('is drawn above the value layers and below the outlines, and is removed with the city', () => {
    const log = []
    const have = new Set()
    const map = {
      getLayer: (id) => (have.has(id) ? {} : undefined),
      getSource: (id) => (have.has(id) ? { setData: () => log.push(`set ${id}`) } : undefined),
      addSource: (id) => have.add(id),
      removeSource: (id) => have.delete(id),
      addLayer: (spec) => have.add(spec.id),
      removeLayer: (id) => have.delete(id),
      moveLayer: (id) => log.push(`move ${id}`),
      setFilter: () => {},
    }
    const layers = [
      { id: 'fua', kind: 'boundary', status: 'ready', type: 'geojson', url: 'x' },
      { id: 'd', kind: 'choropleth', status: 'ready', type: 'pmtiles', url: 'y', source_layer: 's', property: 'v', ramp: { stops: [1], colors: ['#a', '#b'] } },
    ]
    const mask = { type: 'Feature', geometry: { type: 'Polygon', coordinates: [WORLD_RING] } }
    syncOverlays(map, layers, new Set(['fua', 'd']), 'a', null, mask)
    const order = log.filter((l) => l.startsWith('move')).map((l) => l.slice(5))
    const i = order.indexOf(OUTSIDE_LAYER)
    expect(i).toBeGreaterThan(order.indexOf('d:fill'))
    expect(i).toBeLessThan(order.indexOf('fua:line'))
    expect(have.has(OUTSIDE_SOURCE)).toBe(true)
    syncOutside(map, null)
    expect(have.has(OUTSIDE_LAYER) || have.has(OUTSIDE_SOURCE)).toBe(false)
  })
})

describe('the dock', () => {
  it('has the heights of its states, snaps a dragged height to the nearest, steps within the three', () => {
    expect(DOCK_STATES).toEqual(['folded', 'half', 'full'])
    expect(dockHeight('folded', 1000)).toBe(FOLDED_PX)
    expect(dockHeight('half', 1000)).toBe(460)
    expect(dockHeight('full', 1000)).toBe(1000)
    expect(snapDock(60, 1000)).toBe('folded')
    expect(snapDock(300, 1000)).toBe('half')
    expect(snapDock(800, 1000)).toBe('full')
    expect(stepDock('half', +1)).toBe('full')
    expect(stepDock('full', +1)).toBe('full')
    expect(stepDock('folded', -1)).toBe('folded')
    expect(stepDock('nonsense', -1)).toBe('folded')
  })
  it('refits the map when the box changes, but not when the dock goes full', () => {
    expect(refitOnChange('half', 'folded')).toBe(true)
    expect(refitOnChange('folded', 'half')).toBe(true)
    expect(refitOnChange('full', 'half')).toBe(true)
    expect(refitOnChange('half', 'full')).toBe(true)
    expect(refitOnChange('half', 'half')).toBe(false)
  })
  it('goes into the address when it is not half, and old addresses open on half', () => {
    expect(parseDock('full')).toBe('full')
    expect(parseDock('big')).toBeUndefined()
    const layers = [{ id: 'fua', kind: 'boundary', status: 'ready' }]
    const view = initialState(layers)
    expect(hashOfView(null, view, layers, { dock: 'half' })).toBe('')
    expect(hashOfView(null, view, layers, {})).toBe('')
    expect(hashOfView('lodz', view, layers, { dock: 'folded' })).toBe('#a=lodz&d=folded')
    const cat = { agglomerations: [{ id: 'lodz' }], layers }
    expect(resolveHash(readHash('#a=lodz&d=full'), cat).dock).toBe('full')
    expect(resolveHash(readHash('#a=lodz&l=fua'), cat).dock).toBe('half')
    expect(resolveHash(readHash('#d=weird'), cat).dock).toBe('half')
    expect(hashOf({ agg: null, layers: ['fua'], dock: 'full' }, { layers: ['fua'] })).toBe('#d=full')
  })
})

const noop = () => {}
const focus = { focuses: {}, onHover: noop, onToggle: noop, onClear: noop }
const html = (el) => renderToStaticMarkup(el)

describe('legend, chart and dock render', () => {
  it('the legend has the classes with their shares of residents and the scope line, and no dates or sources', () => {
    const l = { ...layer, attribution: 'Źródło X', population_date: '2021', note: 'Nota' }
    const shares = { scopeOf: (id) => scopeData(doc, id, 'a', 'fua'), aggName: 'Wrocław', area: 'fua', onArea: noop }
    const s = html(h(Legend, { layers: [l], focuses: {}, open: true, onOpen: noop, shares, onHover: noop, onToggle: noop, onClear: noop }))
    expect(s).toContain('10 %')
    expect(s).toContain('30 %')
    expect(s).toContain('60 %')   // no data
    expect(s).toContain('mieszkańcy: Wrocław, cały obszar')
    expect(s).toContain('aria-expanded="true"')
    expect(s).not.toContain('Źródło X')
    expect(s).not.toContain('2021')
    expect(s).not.toContain('Wskaż klasę')
  })
  it('a folded legend is one button; with nothing to show there is nothing', () => {
    const s = html(h(MapLegendBox, { open: false, onToggle: noop }, 'x'))
    expect(s).toContain('aria-expanded="false"')
    expect(html(h(Legend, { layers: [], focuses: {}, open: true, onOpen: noop }))).toBe('')
  })
  it('the legend of a layer without numbers has no scope line', () => {
    const shares = { scopeOf: () => null, aggName: null, area: 'fua', onArea: noop }
    const s = html(h(Legend, { layers: [layer], focuses: {}, open: true, onOpen: noop, shares }))
    expect(s).not.toContain('mieszkańcy:')
    expect(s).toContain('mało')
  })
  it('the city chart has a ring, a table with residents and cells, and says what to do', () => {
    const s = html(h(CityClassChart, { layer, doc, aggId: 'a', aggName: 'Wrocław', area: 'fua', onArea: noop, focus }))
    expect(s).toContain('kit-donut')
    expect(s).toContain('kit-split-table')
    expect(s).toContain('brak danych X')
    expect(s).toContain('Razem: 100 mieszkańców, 10 komórek')
    expect(s).toContain('Kliknij klasę')
  })
  it('the city chart sums the pinned classes under the chart', () => {
    const pinned = { ...focus, focuses: { L: togglePinned(EMPTY_FOCUS, 'L', 1) } }
    const s = html(h(CityClassChart, { layer, doc, aggId: 'a', aggName: 'Wrocław', area: 'fua', onArea: noop, focus: pinned }))
    expect(s).toContain('wybrane klasy: 30 % mieszkańców, 30 % komórek')
  })
  it('both charts say so without a value layer, and without numbers for the layer', () => {
    expect(html(h(CityClassChart, { layer: null, doc, area: 'fua', focus }))).toContain('Włącz warstwę wartości')
    expect(html(h(CitiesClassBars, { layer: null, doc, cities: [], names: {}, area: 'fua', focus }))).toContain('Włącz warstwę wartości')
    expect(html(h(CityClassChart, { layer, doc: {}, aggId: 'a', area: 'fua', focus }))).toContain('nie ma liczb')
    expect(html(h(CitiesClassBars, { layer, doc: {}, cities: [], names: {}, area: 'fua', focus, onPickCity: noop }))).toContain('nie ma jeszcze liczb')
  })
  it('the cities chart has one bar per city with a button that selects it', () => {
    const s = html(h(CitiesClassBars, { layer, doc, cities: ['b', 'a'], names: { a: 'Aaa', b: 'Bbb' }, area: 'fua', focus, onPickCity: noop }))
    expect(s.indexOf('Bbb')).toBeLessThan(s.indexOf('Aaa'))
    expect((s.match(/kitx-stack-pick/g) || []).length).toBe(2)
    // bars are shares of the residents with data (b: 50 and 10 of 60 known), the rest is a note at the row's end
    expect(s).toContain('83 %')
    expect(s).toContain('75 %')
    expect(s).toContain('bez danych: 40 %')
    expect(s).toContain('bez danych: 60 %')
    expect(s).not.toContain('50 %')
  })
  it('the dock is a labelled landmark with size buttons; folded, its content is not drawn', () => {
    const base = { map: h('div', { id: 'map' }), onState: noop, label: 'Tabele', title: h('h2', null, 'Tytuł') }
    const half = html(h(DockStage, { ...base, state: 'half' }, h('p', null, 'treść')))
    expect(half).toContain('aria-label="Tabele"')
    expect(half).toContain('treść')
    expect(half).toContain('aria-expanded="true"')
    expect(half).toContain('role="separator"')
    expect(half).toContain('id="map"')
    const folded = html(h(DockStage, { ...base, state: 'folded' }, h('p', null, 'treść')))
    expect(folded).not.toContain('treść')
    expect(folded).toContain('aria-expanded="false"')
    expect(folded).toContain('id="map"')
    const full = html(h(DockStage, { ...base, state: 'full' }, h('p', null, 'treść')))
    expect(full).toContain('kitx-inset-back')
    expect(full).toContain('id="map"')
  })
})
