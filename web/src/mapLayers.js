// Catalog layer -> MapLibre source and style layers. Pure functions (testable
// without a map) plus syncOverlays(), which reconciles a live map with the
// set of layers that should be visible.
import { ANCHOR_LABELS } from './mapStyle'
import { absoluteUrl } from './config'
import { hasValue, rampExpression } from './ramp'

const ACCENT = '#1D4ED8'

// Bottom to top: values first, hatched gaps over them, outlines last.
export const KIND_ORDER = { choropleth: 0, mask: 1, boundary: 2 }

export const sourceId = (layer) => `src-${layer.id}`
export const fillId = (layer) => `${layer.id}:fill`
export const selId = (layer) => `${layer.id}:sel`

export function sourceSpec(layer) {
  const attribution = layer.attribution || undefined
  if (layer.type === 'pmtiles') {
    return { type: 'vector', url: `pmtiles://${absoluteUrl(layer.url)}`, attribution }
  }
  return { type: 'geojson', data: absoluteUrl(layer.url), attribution }
}

const NOT_CORE = ['!=', ['get', 'level'], 'core']
const IS_CORE = ['==', ['get', 'level'], 'core']

/** MapLibre layers (without "source") for one catalog layer, bottom to top. */
export function layerSpecs(layer, selectedId = null) {
  const sl = layer.type === 'pmtiles' && layer.source_layer ? { 'source-layer': layer.source_layer } : {}
  const specs = []
  if (layer.kind === 'choropleth' && layer.ramp && layer.property) {
    specs.push({
      id: fillId(layer), type: 'fill', ...sl,
      filter: hasValue(layer.property),
      paint: { 'fill-color': rampExpression(layer.property, layer.ramp), 'fill-opacity': 0.8 },
    })
    // no data must never look like a zero: hatched, not the lowest colour
    specs.push({
      id: `${layer.id}:nodata`, type: 'fill', ...sl,
      filter: ['!', hasValue(layer.property)],
      paint: { 'fill-pattern': 'hatch', 'fill-opacity': 0.9 },
    })
  } else if (layer.kind === 'mask') {
    specs.push({ id: fillId(layer), type: 'fill', ...sl, paint: { 'fill-pattern': 'hatch', 'fill-opacity': 0.9 } })
  } else if (layer.kind === 'boundary') {
    specs.push({
      id: fillId(layer), type: 'fill', ...sl,
      paint: { 'fill-color': ACCENT, 'fill-opacity': ['case', IS_CORE, 0.1, 0.04] },
    })
    specs.push({
      id: `${layer.id}:line`, type: 'line', ...sl, filter: NOT_CORE,
      layout: { 'line-join': 'round' },
      paint: { 'line-color': ACCENT, 'line-width': 1.5, 'line-opacity': 0.8 },
    })
    specs.push({
      id: `${layer.id}:core`, type: 'line', ...sl, filter: IS_CORE,
      layout: { 'line-join': 'round' },
      paint: { 'line-color': ACCENT, 'line-width': 1, 'line-opacity': 0.55, 'line-dasharray': [3, 2] },
    })
    specs.push({
      id: selId(layer), type: 'line', ...sl, filter: selectionFilter(selectedId),
      layout: { 'line-join': 'round' },
      paint: { 'line-color': ACCENT, 'line-width': 3.2 },
    })
  }
  return specs
}

export const selectionFilter = (selectedId) => ['all', NOT_CORE, ['==', ['get', 'id'], selectedId || '\u0000']]

/**
 * Makes the map show exactly the ready layers in `active`, in KIND_ORDER, just
 * below the labels. Cheap to call again with the same arguments.
 */
export function syncOverlays(map, layers, active, selectedId) {
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
    if (!map.getSource(sourceId(l))) map.addSource(sourceId(l), sourceSpec(l))
    for (const s of layerSpecs(l, selectedId)) {
      if (!map.getLayer(s.id)) map.addLayer({ ...s, source: sourceId(l) }, ANCHOR_LABELS)
    }
  }
  // stacking: moving each one to just below the labels, in order, sorts them
  for (const l of wanted) {
    for (const s of layerSpecs(l)) map.moveLayer(s.id, ANCHOR_LABELS)
    if (l.kind === 'boundary' && map.getLayer(selId(l))) map.setFilter(selId(l), selectionFilter(selectedId))
  }
  return wanted
}
