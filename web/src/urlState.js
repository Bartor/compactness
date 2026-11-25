// The view lives in the address, so a link opens on the same agglomeration, layers and tab. Only what differs from the
// defaults is written.
//   #a=wroclaw&l=fua,density250&v=layer:variant&s=pwdens_census_1km:desc&d=full&m=area&ar=fua&t=wykresy&p=krakow,lodz&@50.06,19.94,11.2
// a=  the city; l=  the ids of the layers drawn (empty: none; old addresses with several value layers or several layers
//     of one overlay group still open, on the first of each); v=  chosen variants of layers that have some.
// ar= the area every number refers to (core | urban_centre | covered | fua; absent: core). An old address with ma= (the
//     area of a metric page) is read as ar= when it has no ar=.
// t=  the panel's tab (the names of the tabs of the view: comparison miary | wykresy; city najwazniejsze | miary |
//     wykresy | przesiadki); absent: the first tab.
// p=  the cities pinned in the charts.
// s=  the sort of the comparison table (the metric whose row orders the cities, and desc / asc); written only in the
//     comparison view. sd= of older addresses is ignored.
// d=  the bottom panel on desktop: folded, half or full; absent (and after a drag to a custom height): half.
// tb= tc= ta= tx=  the table of measures: the set (a preset id n | all | a group id, or a comma list of measure ids), the cities
//     (tt | all | a comma list), the areas, tx=1 rows and columns swapped; written only when they differ from the default.
// m=  the metric whose page is open.
// iso=<originId> (and isc=evening)  the origin picked in "Dokąd dojadę stąd" and the time of day it shows.
// sg=<mode>:<id>,<id>  the speed features selected on the map (features/segments; mode tram | bus | rail).
// @lat,lon,zoom  the map position, written only after the map was moved by hand.

import { activeIds, initialState, stateFromIds, variantsToWrite } from './layerControl'
import { DEFAULT_DOCK, parseDock } from './kitx/dock'
import { parseTableKeys, writeTableKeys } from './features/tables/spec'

const LIST = ','
const DIRS = ['asc', 'desc']
const AREA_KEYS = ['core', 'urban_centre', 'covered', 'fua']

/** "metric:dir" -> {key, dir}; anything else is no sort (undefined). */
export function parseSort(text) {
  if (!text) return undefined
  const i = text.lastIndexOf(':')
  const key = i > 0 ? text.slice(0, i) : ''
  const dir = text.slice(i + 1)
  return key && DIRS.includes(dir) ? { key, dir } : undefined
}

/** {key, dir} -> "metric:dir"; '' for none. */
export const sortText = (sort) => (sort && sort.key && DIRS.includes(sort.dir) ? `${sort.key}:${sort.dir}` : '')

/** "50.06,19.94,11.2" -> {lat, lon, zoom} or undefined. */
export function parseView(text) {
  const p = String(text || '').split(',').map(Number)
  if (p.length !== 3 || p.some((x) => !Number.isFinite(x))) return undefined
  const [lat, lon, zoom] = p
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 && zoom >= 0 && zoom <= 24 ? { lat, lon, zoom } : undefined
}

/** {lat, lon, zoom} -> "50.06,19.94,11.2" (precision that is enough for a link). */
export const viewText = (v) => `${v.lat.toFixed(4)},${v.lon.toFixed(4)},${Number(v.zoom.toFixed(2))}`

/** What the address asks for; absent keys stay undefined. */
export function readHash(hash = typeof window !== 'undefined' ? window.location.hash : '') {
  const q = new URLSearchParams(hash.replace(/^#/, ''))
  const variants = {}
  for (const pair of (q.get('v') || '').split(LIST).filter(Boolean)) {
    const i = pair.indexOf(':')
    if (i > 0) variants[pair.slice(0, i)] = pair.slice(i + 1)
  }
  const at = [...q.keys()].find((k) => k.startsWith('@'))
  const area = q.get('ar') || q.get('ma')
  return {
    agg: q.get('a') || undefined,
    layers: q.has('l') ? q.get('l').split(LIST).filter(Boolean) : undefined,
    variants,
    sort: parseSort(q.get('s')),
    dock: parseDock(q.get('d')),
    metric: q.get('m') || undefined,
    metricArea: q.get('ma') || undefined,
    area: AREA_KEYS.includes(area) ? area : undefined,
    tab: q.get('t') || undefined,
    table: parseTableKeys(q) || undefined,
    pinned: (q.get('p') || '').split(LIST).filter(Boolean),
    mapView: at ? parseView(at.slice(1)) : undefined,
    iso: q.get('iso') || undefined,
    isoScenario: q.get('isc') === 'evening' ? 'evening' : undefined,
    sel: q.get('sg') || undefined,
  }
}

const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x))

/** The hash (with '#', or '' when plain) for a state, given the defaults. `variants` is {layerId: key}. */
export function hashOf({
  agg, layers, variants = {}, sort, table, dock, metric, area, tab, pinned = [], mapView, iso, isoScenario, sel,
}, defaults) {
  const q = new URLSearchParams()
  if (agg) q.set('a', agg)
  const on = [...layers].sort()
  if (!sameSet(on, [...defaults.layers])) q.set('l', on.join(LIST))
  const v = Object.entries(variants).map(([id, k]) => `${id}:${k}`).sort()
  if (v.length) q.set('v', v.join(LIST))
  if (sortText(sort)) q.set('s', sortText(sort))
  if (table) writeTableKeys(q, table)
  if (dock && dock !== DEFAULT_DOCK && parseDock(dock)) q.set('d', dock)
  if (metric) q.set('m', metric)
  if (area && area !== 'core' && AREA_KEYS.includes(area)) q.set('ar', area)
  if (tab) q.set('t', tab)
  if (pinned.length) q.set('p', pinned.join(LIST))
  if (iso) {
    q.set('iso', iso)
    if (isoScenario === 'evening') q.set('isc', 'evening')
  }
  if (sel) q.set('sg', sel)
  // ',' and ':' are fine in a fragment; left unescaped the link stays readable
  let s = q.toString().replace(/%2C/g, ',').replace(/%3A/g, ':')
  if (mapView) s += `${s ? '&' : ''}@${viewText(mapView)}`
  return s ? `#${s}` : ''
}

/**
 * The hash of the page state: `view` is the layer-control state (layerControl.js), `extra` has the rest of what
 * hashOf takes (sort, dock, metric, area, tab, pinned, mapView).
 */
export function hashOfView(agg, view, layers, extra = {}) {
  const defaults = { layers: [...activeIds(initialState(layers), layers)] }
  const active = activeIds(view, layers)
  return hashOf({ agg, layers: [...active], variants: variantsToWrite(view, layers, active), ...extra }, defaults)
}

/**
 * Checks a parsed hash against the catalog; anything unknown falls back. Returns {agg, state, sort, dock, metric,
 * metricArea, area, tab, pinned, mapView}; the sort is {key, dir} or null, the dock a state (an old address without one
 * gets the half state), the area the old ma= when the address has no ar=. Keys are not checked here: a table ignores a
 * key it has no row for, and the app drops a city or a tab it does not know.
 */
export function resolveHash(parsed, { agglomerations, layers }) {
  const agg = agglomerations.some((a) => a.id === parsed.agg) ? parsed.agg : null
  const state = parsed.layers ? stateFromIds(parsed.layers, layers, parsed.variants) : initialState(layers)
  return {
    agg, state,
    sort: parsed.sort ?? null,
    dock: parsed.dock ?? DEFAULT_DOCK,
    metric: parsed.metric ?? null,
    metricArea: parsed.metricArea ?? null,
    area: parsed.area ?? 'core',
    tab: parsed.tab ?? null,
    table: parsed.table ?? null,
    pinned: (parsed.pinned || []).filter((id) => agglomerations.some((a) => a.id === id)),
    mapView: parsed.mapView ?? null,
    iso: parsed.iso ?? null,
    isoScenario: parsed.isoScenario ?? null,
    sel: parsed.sel ?? null,
  }
}
