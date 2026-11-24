// MapLibre specs that draw one selected node on the dark basemap: its walking paths (one line per stored path), the
// crossings on them coloured by AMPTI W6 class, the starts of steps, and its stops with their names. One GeoJSON
// source; the layers filter it by `k` (kind). Pure builders plus three thin helpers that take the map object.
import { W6 } from './detailData'

export const DETAIL_SOURCE = 'node-detail'
export const LAYER_IDS = {
  paths: 'node-detail:paths',
  hot: 'node-detail:path-hot',
  xings: 'node-detail:xings',
  steps: 'node-detail:steps',
  stops: 'node-detail:stops',
  labels: 'node-detail:labels',
}
export const PATH_COLOR = '#9DB8E8'
export const HOT_COLOR = '#FCD76B'
export const STEPS_COLOR = '#C9A7F5'
export const STOP_FILL = '#F4F6FA'
export const STOP_STROKE = '#1c1f26'
const NONE = -1   // filter value when no path is lit

const point = (lon, lat, props) => ({ type: 'Feature', properties: props, geometry: { type: 'Point', coordinates: [lon, lat] } })

/** FeatureCollection of a decoded node (detailData.decodeNode); empty for null. */
export function detailFeatures(node) {
  const f = []
  if (!node) return { type: 'FeatureCollection', features: f }
  for (const p of node.paths) {
    if (p.coords.length >= 2) {
      f.push({ type: 'Feature', properties: { k: 'path', i: p.i, m: p.m, t: p.min }, geometry: { type: 'LineString', coordinates: p.coords } })
    }
    for (const x of p.xings) f.push(point(x.lon, x.lat, { k: 'x', i: p.i, cls: x.cls }))
    for (const s of p.steps) f.push(point(s.lon, s.lat, { k: 'step', i: p.i }))
  }
  for (const s of node.stops) f.push(point(s.lon, s.lat, { k: 'stop', i: s.i, name: s.name }))
  return { type: 'FeatureCollection', features: f }
}

/** circle-color by W6 class. */
export const w6ColorExpression = () => [
  'match', ['get', 'cls'],
  ...Object.entries(W6).flatMap(([k, v]) => (k === 'unknown' ? [] : [k, v.color])),
  W6.unknown.color,
]

/** The layers, bottom to top (each with source DETAIL_SOURCE). */
export function detailLayerSpecs() {
  return [
    {
      id: LAYER_IDS.paths, type: 'line', source: DETAIL_SOURCE, filter: ['==', ['get', 'k'], 'path'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': PATH_COLOR, 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 2, 18, 4], 'line-opacity': 0.55 },
    },
    {
      id: LAYER_IDS.hot, type: 'line', source: DETAIL_SOURCE, filter: ['all', ['==', ['get', 'k'], 'path'], ['==', ['get', 'i'], NONE]],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': HOT_COLOR, 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 4, 18, 7], 'line-opacity': 1 },
    },
    {
      id: LAYER_IDS.steps, type: 'circle', source: DETAIL_SOURCE, filter: ['==', ['get', 'k'], 'step'],
      paint: { 'circle-color': STEPS_COLOR, 'circle-radius': 4, 'circle-stroke-color': STOP_STROKE, 'circle-stroke-width': 1.5 },
    },
    {
      id: LAYER_IDS.xings, type: 'circle', source: DETAIL_SOURCE, filter: ['==', ['get', 'k'], 'x'],
      paint: {
        'circle-color': w6ColorExpression(), 'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 3.5, 18, 6],
        'circle-stroke-color': STOP_STROKE, 'circle-stroke-width': 1,
      },
    },
    {
      id: LAYER_IDS.stops, type: 'circle', source: DETAIL_SOURCE, filter: ['==', ['get', 'k'], 'stop'],
      paint: { 'circle-color': STOP_FILL, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 4, 18, 7], 'circle-stroke-color': STOP_STROKE, 'circle-stroke-width': 1.5 },
    },
    {
      id: LAYER_IDS.labels, type: 'symbol', source: DETAIL_SOURCE, filter: ['==', ['get', 'k'], 'stop'], minzoom: 15.5,
      layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-offset': [0, 1.1], 'text-anchor': 'top', 'text-optional': true },
      paint: { 'text-color': '#E6E9EF', 'text-halo-color': STOP_STROKE, 'text-halo-width': 1.2 },
    },
  ]
}

/** Filter of the lit path: the path of a movement (index into node.paths), or none. */
export const hotFilter = (pathIndex) => ['all', ['==', ['get', 'k'], 'path'], ['==', ['get', 'i'], Number.isInteger(pathIndex) && pathIndex >= 0 ? pathIndex : NONE]]

/** Adds or refreshes the source and the layers for `node` (decoded); `before` = a layer id to insert under. */
export function showNodeDetail(map, node, before) {
  const data = detailFeatures(node)
  const src = map.getSource(DETAIL_SOURCE)
  if (src) src.setData(data)
  else map.addSource(DETAIL_SOURCE, { type: 'geojson', data })
  for (const spec of detailLayerSpecs()) {
    if (!map.getLayer(spec.id)) map.addLayer(spec, before && map.getLayer(before) ? before : undefined)
  }
}

/** Lights one path (or none with null / -1). */
export function setHotPath(map, pathIndex) {
  if (map.getLayer(LAYER_IDS.hot)) map.setFilter(LAYER_IDS.hot, hotFilter(pathIndex))
}

/** Removes the layers and the source. */
export function clearNodeDetail(map) {
  for (const id of Object.values(LAYER_IDS).reverse()) if (map.getLayer(id)) map.removeLayer(id)
  if (map.getSource(DETAIL_SOURCE)) map.removeSource(DETAIL_SOURCE)
}

/** [west, south, east, north] of everything drawn, for fitBounds; null when nothing. */
export function detailBounds(node) {
  const pts = []
  for (const s of node?.stops || []) pts.push([s.lon, s.lat])
  for (const p of node?.paths || []) for (const c of p.coords) pts.push(c)
  if (!pts.length) return null
  let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity]
  for (const [x, y] of pts) { w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y) }
  return [w, s, e, n]
}
