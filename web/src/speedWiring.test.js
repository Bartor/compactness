import { describe, expect, it } from 'vitest'
import {
  activeIds, initialState, overlayGroups, revealLayer, setGroupVariant, setLayerOn, setOverlayOn, sharedVariant,
  stateFromIds, variantOf, variantsToWrite,
} from './layerControl'
import { KIND_ORDER, layerSpecs, syncOverlays } from './mapLayers'
import { hashOf, readHash, resolveHash } from './urlState'
import { resolvedLayer } from './features/speed/loader'
import { topNodes } from './metricTable'

const V = ['w_am', 'w_md', 's_mo'].map((key) => ({ key, label: key }))
const L = (id, kind, extra = {}) => ({ id, kind, status: 'ready', title: id, ...extra })
const layers = [
  L('fua', 'boundary'),
  L('speed_tram', 'lines', { mode_group: 'tram', url: 'data/speed/trams.geojson', variants: V, property: 'v' }),
  L('speed_bus', 'lines', { type: 'geojson', mode_group: 'bus', url_template: 'data/speed/bus_{agg}.geojson', needs_city: true, cities: ['krakow'], variants: V }),
  L('speed_rail', 'lines', { mode_group: 'rail', url: 'data/speed/rail.geojson', variants: V }),
]
const ids = (s) => [...s].sort()

describe('the speed overlay group ("lines")', () => {
  it('is one group of independent switches, all off at first', () => {
    const g = overlayGroups(layers).find((x) => x.kind === 'lines')
    expect(g.layers.map((l) => l.id)).toEqual(['speed_tram', 'speed_bus', 'speed_rail'])
    expect(ids(activeIds(initialState(layers), layers))).toEqual(['fua'])
  })
  it('switches layers one by one; the group-wide switch does nothing', () => {
    let s = setLayerOn(initialState(layers), 'lines', 'speed_tram', true, layers)
    s = setLayerOn(s, 'lines', 'speed_rail', true, layers)
    expect(ids(activeIds(s, layers))).toEqual(['fua', 'speed_rail', 'speed_tram'])
    expect(setOverlayOn(s, 'lines', false)).toBe(s)
    s = setLayerOn(s, 'lines', 'speed_tram', false, layers)
    expect(ids(activeIds(s, layers))).toEqual(['fua', 'speed_rail'])
    expect(setLayerOn(s, 'lines', 'nope', true, layers)).toBe(s)
  })
  it('one band for all of them', () => {
    let s = setGroupVariant(initialState(layers), 'lines', 's_mo', layers)
    expect(layers.filter((l) => l.kind === 'lines').map((l) => variantOf(s, l))).toEqual(['s_mo', 's_mo', 's_mo'])
    expect(sharedVariant(s, 'lines', layers)).toBe('s_mo')
    s = setGroupVariant(s, 'lines', 'nope', layers)   // a band the layers do not offer is ignored
    expect(sharedVariant(s, 'lines', layers)).toBe('s_mo')
  })
  it('an address lists the layers that are on and their band; revealing a layer switches only that one on', () => {
    const s = stateFromIds(['speed_tram', 'speed_bus'], layers, { speed_tram: 'w_md', speed_bus: 'w_md' })
    expect(ids(activeIds(s, layers))).toEqual(['speed_bus', 'speed_tram'])
    expect(variantsToWrite(s, layers, activeIds(s, layers))).toEqual({ speed_tram: 'w_md', speed_bus: 'w_md' })
    expect(ids(activeIds(revealLayer(initialState(layers), layers, 'speed_rail'), layers))).toEqual(['fua', 'speed_rail'])
  })
  it('round trips through the address', () => {
    const catalog = { layers, agglomerations: [{ id: 'krakow' }] }
    const s = setLayerOn(initialState(layers), 'lines', 'speed_tram', true, layers)
    const h = hashOf({ agg: 'krakow', layers: [...activeIds(s, layers)], variants: { speed_tram: 'w_md' } }, { layers: ['fua'] })
    const back = resolveHash(readHash(h), catalog)
    expect(ids(activeIds(back.state, layers))).toEqual(['fua', 'speed_tram'])
    expect(variantOf(back.state, layers[1])).toBe('w_md')
  })
})

describe('drawing the speed layers', () => {
  it('lines sit above the hatch and below the stop areas; their specs carry the band', () => {
    expect(KIND_ORDER.lines).toBeGreaterThan(KIND_ORDER.mask)
    expect(KIND_ORDER.lines).toBeLessThan(KIND_ORDER.points)
    const specs = layerSpecs({ ...layers[1], band: 's_mo' })
    expect(specs.length).toBeGreaterThan(2)
    expect(JSON.stringify(specs)).toContain('v_s_mo')
  })
  it('the bus file belongs to the selected city; without one or for another city the layer has no url', () => {
    expect(resolvedLayer(layers[2], 'krakow').url).toBe('data/speed/bus_krakow.geojson')
    expect(resolvedLayer(layers[2], null)).toBeNull()
    expect(resolvedLayer(layers[2], 'opole')).toBeNull()
  })
  it('a layer without a url is not drawn, and one whose file changed gets the new data', () => {
    const calls = []
    const sources = {}
    const lay = {}
    const map = {
      getLayer: (id) => lay[id], getSource: (id) => sources[id],
      addSource: (id, spec) => { sources[id] = { setData: (d) => calls.push(['setData', d]), spec } },
      addLayer: (s) => { lay[s.id] = s }, removeLayer: (id) => { delete lay[id] }, removeSource: (id) => { delete sources[id] },
      moveLayer: () => {}, setFilter: () => {},
    }
    const bus = (url) => [{ ...layers[2], url, band: 'w_am' }]
    syncOverlays(map, bus(null), new Set(['speed_bus']), null)
    expect(Object.keys(sources)).toEqual([])
    syncOverlays(map, bus('data/speed/bus_krakow.geojson'), new Set(['speed_bus']), null)
    expect(Object.keys(sources)).toEqual(['src-speed_bus'])
    syncOverlays(map, bus('data/speed/bus_lodz.geojson'), new Set(['speed_bus']), null)
    expect(calls).toHaveLength(1)
    expect(calls[0][1]).toContain('bus_lodz')
  })
})

describe('stop areas ordered by transfer use', () => {
  const f = (id, dep, use) => ({ properties: { id, name: id, agg: 'a', dep_h: dep, use, use_ok: true }, geometry: { type: 'Point', coordinates: [0, 0] } })
  it('orders by departures or by use', () => {
    const feats = [f('x', 100, 0.1), f('y', 50, 0.4), f('z', 80, 0.2)]
    expect(topNodes(feats, 'a', 3, 'dep').map((n) => n.id)).toEqual(['x', 'z', 'y'])
    expect(topNodes(feats, 'a', 3, 'use').map((n) => n.id)).toEqual(['y', 'z', 'x'])
  })
})

describe('the sidebar controls of speed and isochrones', () => {
  const view = initialState(layers)
  const base = { catalog: { layers, agglomerations: [] }, view, onValue: () => {}, onOverlayOn: () => {}, onOverlayLayer: () => {}, onVariant: () => {}, sheetOpen: false, setSheetOpen: () => {}, onAbout: () => {} }
  it('the bus switch is disabled and says why while no city is selected; the chooser appears with a layer on', async () => {
    const { createElement: h } = await import('react')
    const { renderToStaticMarkup } = await import('react-dom/server')
    const Sidebar = (await import('./Sidebar')).default
    const s = renderToStaticMarkup(h(Sidebar, { ...base, agg: null, iso: { on: false, enabled: false, onChange: () => {} } }))
    expect(s).toContain('Prędkość z rozkładu')
    expect(s).toContain('wybierz miasto, aby zobaczyć autobusy')
    expect(s).toContain('Wybierz najpierw aglomerację')           // why the isochrone switch is off
    expect(s).toContain('Dokąd dojadę stąd')
    expect(s).not.toContain('szczyt poranny')                    // no chooser while nothing is on
    const on = setLayerOn(view, 'lines', 'speed_tram', true, layers)
    const s2 = renderToStaticMarkup(h(Sidebar, { ...base, view: on, agg: 'krakow' }))
    expect(s2).toContain('środa')
    expect(s2).not.toContain('wybierz miasto, aby zobaczyć autobusy')
  })
})
