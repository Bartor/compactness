import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import {
  bandLabel, cardRows, decodeRing, distanceM, formatDistance, formatResidents, isoGeoJSON, nearestOrigin, originGeoJSON,
} from './isoModel'
import { BAND_STYLE, ISO_LAYERS, isoLayerSpecs, syncIsochrones, bandLegend } from './isoLayers'
import { isoUrl, loadIsochrones, clearIsoCache, validIsoFile } from './isoData'
import IsochroneCard from './IsochroneCard'

// encoded by pipeline.isochrones.encode_polyline: (51.1083, 17.0403), (51.11, 17.032), (51.1, 17.03)
const RING = '{a}vH{d_gBsIzr@n}@nK'

const FILE = {
  agglomeration: 'wroclaw', day: '2026-11-25',
  scenarios: { am: { minutes: [15, 30, 45, 60] }, evening: { minutes: [15, 30, 45, 60] }, walk: { minutes: [15, 30] } },
  origins: [
    { id: 'hub', kind: 'hub', name: 'Galeria Dominikańska', lon: 17.0403, lat: 51.1083 },
    { id: 'g1-17-5662', kind: 'grid', name: 'siatka 1 km', lon: 16.98, lat: 51.12 },
  ],
  iso: {
    hub: {
      am: { residents: [100, 2000, 30000, 400000], residents_band: [100, 1900, 28000, 370000], geom: [[[RING]], [[RING]], [], [[RING, RING]]] },
      evening: { residents: [90, 1500, 25000, 350000], residents_band: [90, 1410, 23500, 325000], geom: [[], [], [], []] },
      walk: { residents: [50, 900], residents_band: [50, 850], geom: [[[RING]], []] },
    },
  },
}

describe('polyline decoding', () => {
  it('matches the reference example of the format and returns [lon, lat], closed', () => {
    const r = decodeRing('_p~iF~ps|U_ulLnnqC_mqNvxq`@')
    expect(r.slice(0, 3)).toEqual([[-120.2, 38.5], [-120.95, 40.7], [-126.453, 43.252]])
    expect(r[3]).toEqual(r[0])
  })
  it('reads what the Python encoder wrote', () => {
    const r = decodeRing(RING)
    expect(r[0]).toEqual([17.0403, 51.1083])
    expect(r[2]).toEqual([17.03, 51.1])
    expect(r).toHaveLength(4)
  })
})

describe('nearest origin', () => {
  it('picks the closest precomputed point and reports the distance', () => {
    const n = nearestOrigin(FILE.origins, [16.981, 51.1201])
    expect(n.origin.id).toBe('g1-17-5662')
    expect(n.distanceM).toBeGreaterThan(50)
    expect(n.distanceM).toBeLessThan(100)
  })
  it('is null without origins', () => expect(nearestOrigin([], [17, 51])).toBeNull())
  it('measures metres sensibly', () => {
    // 0.01 deg of latitude ~ 1.11 km
    expect(Math.round(distanceM([17, 51], [17, 51.01]))).toBeGreaterThan(1100)
    expect(Math.round(distanceM([17, 51], [17, 51.01]))).toBeLessThan(1125)
  })
})

describe('GeoJSON of an origin', () => {
  it('gives one feature per band, largest first, with Polish labels and residents', () => {
    const g = isoGeoJSON(FILE, 'hub', 'am')
    expect(g.features.map((f) => f.properties.minutes)).toEqual([60, 45, 30, 15])
    expect(g.features[3].properties.label).toBe('do 15 min')
    expect(g.features[0].properties.residents).toBe(400000)
    expect(g.features[0].geometry.coordinates[0]).toHaveLength(2)   // outer ring and one hole
    expect(g.features[1].geometry.coordinates).toEqual([])          // an empty band stays an empty MultiPolygon
  })
  it('walk has only its two bands; unknown origins give null', () => {
    expect(isoGeoJSON(FILE, 'hub', 'walk').features).toHaveLength(2)
    expect(isoGeoJSON(FILE, 'nope', 'am')).toBeNull()
    expect(originGeoJSON(FILE.origins[0]).features[0].geometry.coordinates).toEqual([17.0403, 51.1083])
  })
})

describe('card numbers', () => {
  it('lists cumulative residents per band, walk only up to 30 min', () => {
    const rows = cardRows(FILE, 'hub')
    expect(rows.map((r) => r.label)).toEqual(['do 15 min', 'do 30 min', 'do 45 min', 'do 60 min'])
    expect(rows[1]).toMatchObject({ am: 2000, evening: 1500, walk: 900 })
    expect(rows[3].walk).toBeNull()
  })
  it('formats residents and distances in Polish; missing is a dash, never 0', () => {
    expect(formatResidents(null)).toBe('–')
    expect(formatResidents(0)).toBe('0')
    expect(formatResidents(950)).toBe('950')
    expect(formatResidents(12345).replace(/\s/g, ' ')).toBe('12,3 tys.')
    expect(formatResidents(254367)).toBe('254 tys.')
    expect(formatResidents(1250000)).toBe('1,25 mln')
    expect(formatDistance(420)).toBe('420 m')
    expect(formatDistance(1234)).toBe('1,2 km')
    expect(bandLabel(45)).toBe('do 45 min')
  })
})

describe('map layers', () => {
  it('outer bands are lighter (more transparent) than inner ones', () => {
    const op = [15, 30, 45, 60].map((m) => BAND_STYLE[m].opacity)
    expect([...op].sort((a, b) => b - a)).toEqual(op)
    expect(bandLegend().map((b) => b.label)).toEqual(['do 15 min', 'do 30 min', 'do 45 min', 'do 60 min'])
  })
  it('draws fills under lines and labels, the origin on top, every layer with a source', () => {
    const ids = isoLayerSpecs().map((s) => s.id)
    expect(ids.indexOf(ISO_LAYERS.fill)).toBeLessThan(ids.indexOf(ISO_LAYERS.line))
    expect(ids[ids.length - 1]).toBe(ISO_LAYERS.originLabel)
    expect(isoLayerSpecs().every((s) => s.source)).toBe(true)
  })
  it('syncIsochrones adds, updates and removes sources and layers', () => {
    const sources = new Map()
    const layers = []
    const map = {
      getSource: (id) => sources.get(id),
      addSource: (id, s) => sources.set(id, { ...s, setData(d) { this.data = d } }),
      removeSource: (id) => sources.delete(id),
      getLayer: (id) => layers.find((l) => l.id === id),
      addLayer: (l) => layers.push(l),
      removeLayer: (id) => layers.splice(layers.findIndex((l) => l.id === id), 1),
      moved: 0,
      moveLayer() { this.moved += 1 },
    }
    const iso = { bands: isoGeoJSON(FILE, 'hub', 'am'), walk: isoGeoJSON(FILE, 'hub', 'walk'), origin: originGeoJSON(FILE.origins[0]) }
    expect(syncIsochrones(map, iso, 'label-water')).toBe(true)
    expect(layers).toHaveLength(isoLayerSpecs().length)
    expect(sources.size).toBe(3)
    syncIsochrones(map, { ...iso, bands: isoGeoJSON(FILE, 'hub', 'evening') })
    expect(layers).toHaveLength(isoLayerSpecs().length)
    expect(map.moved).toBe(isoLayerSpecs().length)   // restacked on the second call
    syncIsochrones(map, null)
    expect(layers).toHaveLength(0)
    expect(sources.size).toBe(0)
  })
})

describe('loading', () => {
  it('builds the URL under data/isochrones/', () => expect(isoUrl('lodz', './data/')).toBe('./data/isochrones/lodz.json'))
  it('returns null for a missing or malformed file and the file when it is valid', async () => {
    clearIsoCache()
    const fetchImpl = async (u) => (u.includes('gzm')
      ? { ok: false }
      : { ok: true, json: async () => (u.includes('bad') ? { foo: 1 } : FILE) })
    expect(await loadIsochrones('gzm', { fetchImpl })).toBeNull()
    expect(await loadIsochrones('bad', { fetchImpl })).toBeNull()
    expect(await loadIsochrones('wroclaw', { fetchImpl })).toBe(FILE)
    expect(validIsoFile(null)).toBe(false)
  })
})

describe('the card', () => {
  const html = (p) => renderToStaticMarkup(h(IsochroneCard, p))
  it('asks for a click before an origin is picked', () => {
    expect(html({ file: FILE, status: 'ready', origin: null })).toContain('Kliknij na mapie')
  })
  it('says when a city has no file', () => {
    expect(html({ file: null, status: 'missing' })).toContain('nie ma wyliczonych zasięgów')
  })
  it('shows the origin, the distance, the residents and the limits', () => {
    const s = html({ file: FILE, status: 'ready', origin: FILE.origins[0], distanceM: 640, scenario: 'evening' })
    expect(s).toContain('Galeria Dominikańska')
    expect(s).toContain('640 m od kliknięcia')
    expect(s).toContain('do 60 min')
    expect(s).toContain('400 tys.')
    expect(s).toContain('aria-checked="true" class="on">wieczorem')
    expect(s).toContain('najbliższy wyliczony punkt')
    expect(s).toContain('nie rzeczywiste')
  })
})
