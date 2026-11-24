// Catalog layer -> MapLibre source and style layers. Pure functions (testable
// without a map) plus syncOverlays(), which reconciles a live map with the
// set of layers that should be visible.
import { ANCHOR_LABELS } from './mapStyle'
import { absoluteUrl } from './config'
import { hasValue, rampExpression } from './ramp'
import { pointSpecs } from './pointLayers'
import { lineSpecs } from './features/speed/lineLayers'

// City outlines on a dark basemap: light blue, the selected city white, the hovered one in between.
export const OUTLINE = '#9DB8E8'
export const OUTLINE_HOT = '#CFE0FF'
export const OUTLINE_SELECTED = '#FFFFFF'

// Bottom to top: values first, hatched gaps over them, stop areas, outlines last.
export const KIND_ORDER = { choropleth: 0, mask: 1, lines: 1.5, points: 2, boundary: 3 }

export const sourceId = (layer) => `src-${layer.id}`
export const fillId = (layer) => `${layer.id}:fill`
export const selId = (layer) => `${layer.id}:sel`
export const hotId = (layer) => `${layer.id}:hot`
export const OUTSIDE_SOURCE = 'outside-src'
export const OUTSIDE_LAYER = 'outside:fill'
// the veil over everything outside the selected city: dark, so that the city stands out without hiding the rest
export const OUTSIDE_COLOR = '#12141a'
export const OUTSIDE_OPACITY = 0.62

export function sourceSpec(layer) {
  const attribution = layer.attribution || undefined
  if (layer.type === 'pmtiles') {
    return { type: 'vector', url: `pmtiles://${absoluteUrl(layer.url)}`, attribution }
  }
  return { type: 'geojson', data: absoluteUrl(layer.url), attribution }
}

const NOT_CORE = ['!=', ['get', 'level'], 'core']
const IS_CORE = ['==', ['get', 'level'], 'core']
const ZERO = ['==', ['get', 'id'], '\u0000']   // matches nothing: the filter of a highlight that is off

/** MapLibre layers (without "source") for one catalog layer, bottom to top. */
export function layerSpecs(layer, selectedId = null, hot = null) {
  const sl = layer.type === 'pmtiles' && layer.source_layer ? { 'source-layer': layer.source_layer } : {}
  const specs = []
  if (layer.kind === 'choropleth' && layer.ramp && layer.property) {
    specs.push({
      id: fillId(layer), type: 'fill', ...sl,
      filter: hasValue(layer.property),
      paint: { 'fill-color': rampExpression(layer.property, layer.ramp), 'fill-opacity': layer.opacity ?? 0.8 },
    })
    // no data must never look like a zero: hatched, not the lowest colour
    specs.push({
      id: `${layer.id}:nodata`, type: 'fill', ...sl,
      filter: ['!', hasValue(layer.property)],
      paint: { 'fill-pattern': 'hatch', 'fill-opacity': 0.9 },
    })
  } else if (layer.kind === 'points') {
    specs.push(...pointSpecs(layer))
  } else if (layer.kind === 'lines') {
    specs.push(...lineSpecs(layer, layer.band || undefined))
  } else if (layer.kind === 'mask') {
    specs.push({ id: fillId(layer), type: 'fill', ...sl, paint: { 'fill-pattern': 'hatch', 'fill-opacity': 0.9 } })
  } else if (layer.kind === 'boundary') {
    // Outlines only. The fill is the invisible hit area that queryRenderedFeatures finds: MapLibre's query looks
    // at geometry and filters, not at paint, so a fill at opacity 0 is still hit (and not drawn).
    specs.push({
      id: fillId(layer), type: 'fill', ...sl,
      paint: { 'fill-color': OUTLINE, 'fill-opacity': 0 },
    })
    specs.push({
      id: `${layer.id}:line`, type: 'line', ...sl, filter: NOT_CORE,
      layout: { 'line-join': 'round' },
      paint: { 'line-color': OUTLINE, 'line-width': 1.6, 'line-opacity': 0.85 },
    })
    specs.push({
      id: `${layer.id}:core`, type: 'line', ...sl, filter: IS_CORE,
      layout: { 'line-join': 'round' },
      paint: { 'line-color': OUTLINE, 'line-width': 1.2, 'line-opacity': 0.75, 'line-dasharray': [3, 2] },
    })
    // the city under the pointer (or whose column is lit in a table): both its outlines, stronger
    specs.push({
      id: hotId(layer), type: 'line', ...sl, filter: hotFilter(hot),
      layout: { 'line-join': 'round' },
      paint: { 'line-color': OUTLINE_HOT, 'line-width': 2.8, 'line-opacity': 0.95 },
    })
    specs.push({
      id: selId(layer), type: 'line', ...sl, filter: selectionFilter(selectedId),
      layout: { 'line-join': 'round' },
      paint: { 'line-color': OUTLINE_SELECTED, 'line-width': 3.4 },
    })
  }
  return specs
}

export const selectionFilter = (selectedId) => ['all', NOT_CORE, ['==', ['get', 'id'], selectedId || '\u0000']]
export const hotFilter = (hot) => (hot ? ['==', ['get', 'id'], hot] : ZERO)

/**
 * Makes the map show exactly the ready layers in `active`, in KIND_ORDER, just
 * below the labels. Cheap to call again with the same arguments.
 * `outside` (optional) is a GeoJSON Feature that covers everything outside the selected city (outsideMask.js): it is
 * drawn as a dark veil above the value layers, the hatch and the stop areas and below the outlines, so those are
 * dimmed outside the city and the outlines (and so clicks on other cities) are not.
 */
// the url each GeoJSON source of a map was given (a layer whose file depends on the city gets new data when it changes)
const loadedUrl = new WeakMap()

export function syncOverlays(map, layers, active, selectedId, hot = null, outside = null) {
  const wanted = layers
    .filter((l) => l.status === 'ready' && active.has(l.id) && l.url && layerSpecs(l).length)
    .sort((a, b) => (KIND_ORDER[a.kind] ?? 9) - (KIND_ORDER[b.kind] ?? 9))
  const wantedIds = new Set(wanted.map((l) => l.id))

  for (const l of layers) {
    if (wantedIds.has(l.id)) continue
    for (const s of layerSpecs(l)) if (map.getLayer(s.id)) map.removeLayer(s.id)
    if (map.getSource(sourceId(l))) map.removeSource(sourceId(l))
  }
  for (const l of wanted) {
    const urls = loadedUrl.get(map) || {}
    if (!map.getSource(sourceId(l))) map.addSource(sourceId(l), sourceSpec(l))
    else if (l.type === 'geojson' && urls[l.id] && urls[l.id] !== l.url) map.getSource(sourceId(l)).setData(absoluteUrl(l.url))
    urls[l.id] = l.url
    loadedUrl.set(map, urls)
    for (const s of layerSpecs(l, selectedId, hot)) {
      if (!map.getLayer(s.id)) map.addLayer({ ...s, source: sourceId(l) }, ANCHOR_LABELS)
    }
  }
  syncOutside(map, outside)
  const veil = () => { if (map.getLayer(OUTSIDE_LAYER)) map.moveLayer(OUTSIDE_LAYER, ANCHOR_LABELS) }
  let veiled = false
  // stacking: moving each one to just below the labels, in order, sorts them
  for (const l of wanted) {
    if (l.kind === 'boundary' && !veiled) { veil(); veiled = true }
    for (const s of layerSpecs(l)) map.moveLayer(s.id, ANCHOR_LABELS)
    if (l.kind === 'boundary' && map.getLayer(selId(l))) map.setFilter(selId(l), selectionFilter(selectedId))
    if (l.kind === 'boundary' && map.getLayer(hotId(l))) map.setFilter(hotId(l), hotFilter(hot))
  }
  if (!veiled) veil()
  return wanted
}

/** Puts the veil on the map (or updates it), or takes it off when there is none. */
export function syncOutside(map, outside) {
  if (!outside) {
    if (map.getLayer(OUTSIDE_LAYER)) map.removeLayer(OUTSIDE_LAYER)
    if (map.getSource(OUTSIDE_SOURCE)) map.removeSource(OUTSIDE_SOURCE)
    return
  }
  if (map.getSource(OUTSIDE_SOURCE)) map.getSource(OUTSIDE_SOURCE).setData(outside)
  else map.addSource(OUTSIDE_SOURCE, { type: 'geojson', data: outside })
  if (!map.getLayer(OUTSIDE_LAYER)) {
    map.addLayer({
      id: OUTSIDE_LAYER, type: 'fill', source: OUTSIDE_SOURCE,
      paint: { 'fill-color': OUTSIDE_COLOR, 'fill-opacity': OUTSIDE_OPACITY, 'fill-antialias': false },
    }, ANCHOR_LABELS)
  }
}

/** Lights the outline of one city (id) or none (null) on every boundary layer on the map; cheap, no restacking. */
export function applyHot(map, layers, hot) {
  for (const l of layers) {
    if (l.kind === 'boundary' && map.getLayer(hotId(l))) map.setFilter(hotId(l), hotFilter(hot))
  }
}
