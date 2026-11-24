// Point layers (kind "points"): stop areas drawn as circles from a GeoJSON source. Pure functions, testable
// without a map. A node has one colour class (a step over the catalog ramp on `property`), a radius from
// `size_property` (departures per hour) and, without a number in `property`, a hollow grey ring: no data
// never looks like a low value. Which nodes are drawn depends on the zoom (ZOOM_BANDS): the busiest first.
import { focusOpacity, hasValue, rampExpression } from './ramp'

export const NODATA_GREY = '#7C7F86'
export const SIZE_RADII = [3, 4.5, 6.5, 8.5, 11]     // px at zoom 11: below the first size stop, then from each stop
export const ZOOM_SCALE = [[8, 0.85], [14, 1.25]]     // radius factor at a zoom, linear in between
export const BASE_OPACITY = 0.92
export const DIM_OPACITY = 0.12

// Nodes with at least `min` (and below `max`) departures an hour are drawn from `minzoom`; busier nodes are
// therefore drawn at every zoom a quieter band is. One MapLibre layer per band, because a layer's minzoom
// needs no zoom expression in a filter.
export const ZOOM_BANDS = [
  { minzoom: 8, min: 100, max: null },
  { minzoom: 10, min: 50, max: 100 },
  { minzoom: 11.5, min: 20, max: 50 },
  { minzoom: 13, min: null, max: 20 },
]

const dep = (layer) => ['to-number', ['get', layer.size_property || 'dep_h'], 0]

/** Filter of one zoom band. */
export function bandFilter(layer, band) {
  const parts = ['all']
  if (band.min != null) parts.push(['>=', dep(layer), band.min])
  if (band.max != null) parts.push(['<', dep(layer), band.max])
  return parts.length === 1 ? true : parts
}

/** True when a node with `departures` an hour is drawn at `zoom`. */
export const drawnAt = (departures, zoom) => ZOOM_BANDS.some(
  (b) => zoom >= b.minzoom && (b.min == null || departures >= b.min) && (b.max == null || departures < b.max),
)

const round2 = (x) => Math.round(x * 100) / 100

function sized(layer, factor) {
  const stops = layer.size_stops || []
  const e = ['step', dep(layer), round2(SIZE_RADII[0] * factor)]
  stops.forEach((s, i) => e.push(s, round2(SIZE_RADII[Math.min(i + 1, SIZE_RADII.length - 1)] * factor)))
  return e
}

/** circle-radius: a step over departures per hour, scaled mildly with the zoom. */
export function radiusExpression(layer) {
  const [[z0, k0], [z1, k1]] = ZOOM_SCALE
  return ['interpolate', ['linear'], ['zoom'], z0, sized(layer, k0), z1, sized(layer, k1)]
}

/** Size key of the legend: [{radius, label}], radius in px at zoom 11. */
export function sizeClasses(layer) {
  const stops = layer.size_stops || []
  return [null, ...stops].map((from, i) => {
    const to = i < stops.length ? stops[i] : null
    const label = from == null ? `<${stops[0]}` : to == null ? `${from}+` : `${from}–${to}`
    return { radius: SIZE_RADII[Math.min(i, SIZE_RADII.length - 1)], label }
  })
}

export const nodataId = (layer, k) => `${layer.id}:nodata:${k}`
export const pointId = (layer, k) => `${layer.id}:pts:${k}`

/** MapLibre layers (without "source") for one points layer, bottom to top: rings first, then coloured circles. */
export function pointSpecs(layer) {
  if (!layer.ramp || !layer.property) return []
  const order = ZOOM_BANDS.map((_, k) => k).reverse()   // quiet nodes below busy ones
  const radius = radiusExpression(layer)
  const specs = []
  for (const k of order) {
    const band = ZOOM_BANDS[k]
    specs.push({
      id: nodataId(layer, k), type: 'circle', minzoom: band.minzoom,
      filter: ['all', bandFilter(layer, band), ['!', hasValue(layer.property)]],
      paint: {
        'circle-color': 'rgba(0,0,0,0)', 'circle-radius': radius,
        'circle-stroke-color': NODATA_GREY, 'circle-stroke-width': 1.3, 'circle-stroke-opacity': 0.9,
      },
    })
  }
  for (const k of order) {
    const band = ZOOM_BANDS[k]
    specs.push({
      id: pointId(layer, k), type: 'circle', minzoom: band.minzoom,
      filter: ['all', bandFilter(layer, band), hasValue(layer.property)],
      paint: {
        'circle-color': rampExpression(layer.property, layer.ramp), 'circle-radius': radius,
        'circle-opacity': BASE_OPACITY, 'circle-stroke-color': '#FFFFFF', 'circle-stroke-width': 0.8,
        'circle-stroke-opacity': 1,
      },
    })
  }
  return specs
}

export const pointLayerIds = (layer) => pointSpecs(layer).map((s) => s.id)

/**
 * Paint values for a given focus (a Set of emphasised class indices, empty = none): the classes not
 * emphasised fade (fill and stroke), and so do the rings.
 */
export function focusPaint(layer, strong) {
  return {
    fill: focusOpacity(layer.property, layer.ramp, strong, BASE_OPACITY, DIM_OPACITY),
    stroke: focusOpacity(layer.property, layer.ramp, strong, 1, 0.15),
    ring: strong && strong.size ? 0.2 : 0.9,
  }
}

/** Applies focusPaint to the layers that exist on the map. */
export function applyFocus(map, layer, strong) {
  const p = focusPaint(layer, strong)
  ZOOM_BANDS.forEach((_, k) => {
    if (map.getLayer(pointId(layer, k))) {
      map.setPaintProperty(pointId(layer, k), 'circle-opacity', p.fill)
      map.setPaintProperty(pointId(layer, k), 'circle-stroke-opacity', p.stroke)
    }
    if (map.getLayer(nodataId(layer, k))) map.setPaintProperty(nodataId(layer, k), 'circle-stroke-opacity', p.ring)
  })
}
