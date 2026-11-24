// MapLibre layer specs for catalog layers of kind "lines" (scheduled speed of stretches and lines). Pure functions,
// testable without a map, plus small helpers that apply hover / pin fading and hit-test the map.
//
// A stretch direction is one feature. Colour: the fixed speed class of the selected band (`v_<band>`); width: trips
// per hour in that band (`t_<band>`, the catalog's `size_property` prefix); each direction is drawn offset to its
// right (line-offset), so both directions of a street show side by side; dashed when flagged (below the 5-minute
// minimum, straight-line geometry or an unofficial feed). Trams and rail from zoom 10, buses from 12; quiet
// stretches (fewer than QUIET_TPH trips an hour) QUIET_DELAY zoom levels later. A stretch without trips in the band
// is not drawn (no service is not "no data"; the legend says so).
import { CLASS_COLORS, CLASS_BREAKS, DEFAULT_BAND, classOf, featureLineKeys, props } from './speedModel'

export const MINZOOM = { tram: 8, rail: 8, bus: 11 }      // trams and rail must show at the zoom a city is fitted to
export const QUIET_TPH = 4
export const QUIET_DELAY = 1.5
export const WIDTH_STOPS = [4, 8, 15, 30]          // trips an hour where the width steps up
export const WIDTHS = [1.2, 2, 3, 4.2, 5.5]        // px at zoom 13
export const ZOOM_WIDTH = [[8, 0.5], [16, 1.8]]   // width factor at a zoom, linear in between
export const BASE_OPACITY = 0.95
export const DIM_OPACITY = 0.12
export const HOT_COLOR = '#FFFFFF'

/** Which zoom rule a layer follows: from the catalog's `mode_group` ("tram" | "bus" | "rail"). */
export const groupOf = (layer) => layer?.mode_group || 'tram'

const FLAGGED = ['any', ['has', 'short'], ['has', 'straight'], ['has', 'unoff']]
const hasNum = (p) => ['==', ['typeof', ['get', p]], 'number']
const tph = (band) => ['to-number', ['get', props(band).t], 0]

/** line-color: a step over the band's speed on the fixed classes. */
export function colorExpression(band = DEFAULT_BAND) {
  const e = ['step', ['get', props(band).v], CLASS_COLORS[0]]
  CLASS_BREAKS.forEach((b, i) => e.push(b, CLASS_COLORS[i + 1]))
  return e
}

const r2 = (x) => Math.round(x * 100) / 100

function widthAt(band, factor) {
  const e = ['step', tph(band), r2(WIDTHS[0] * factor)]
  WIDTH_STOPS.forEach((s, i) => e.push(s, r2(WIDTHS[i + 1] * factor)))
  return e
}

/** line-width: a step over trips per hour, scaled with the zoom. */
export function widthExpression(band = DEFAULT_BAND) {
  const [[z0, k0], [z1, k1]] = ZOOM_WIDTH
  return ['interpolate', ['linear'], ['zoom'], z0, widthAt(band, k0), z1, widthAt(band, k1)]
}

/** line-offset: half the width plus a gap, to the right of the drawing direction (rail lines are not offset). */
export function offsetExpression(band = DEFAULT_BAND, group = 'tram') {
  if (group === 'rail') return 0
  const [[z0, k0], [z1, k1]] = ZOOM_WIDTH
  const half = (k) => ['+', ['/', widthAt(band, k), 2], r2(0.6 * k)]
  return ['interpolate', ['linear'], ['zoom'], z0, half(k0), z1, half(k1)]
}

export const lineId = (layer, tier, dashed) => `${layer.id}:${tier}:${dashed ? 'dash' : 'solid'}`
export const hotLineId = (layer) => `${layer.id}:hot`
export const TIERS = ['busy', 'quiet']

/** Filter of one tier x style for the band. */
export function tierFilter(band, tier, dashed) {
  return ['all', hasNum(props(band).v),
    tier === 'busy' ? ['>=', tph(band), QUIET_TPH] : ['<', tph(band), QUIET_TPH],
    dashed ? FLAGGED : ['!', FLAGGED]]
}

/** Filter that matches nothing (a highlight that is off). */
export const NONE = ['==', ['get', 'id'], '\u0000']

/**
 * Filter of the features that carry any of the line-table row keys ("agg|feed|line"): the stretches of lines
 * hovered or pinned in the table. Uses substring tests on the comma-fenced `ln` and on `fd`.
 */
export function linesFilter(keys) {
  if (!keys || !keys.length) return NONE
  const any = ['any']
  for (const k of [...new Set(keys)].sort()) {
    const [agg, feed, line] = String(k).split('|')
    if (!agg || !line) continue
    any.push(['all', ['==', ['get', 'agg'], agg], ['in', feed || '', ['to-string', ['get', 'fd']]],
      ['in', `,${line},`, ['to-string', ['get', 'ln']]]])
  }
  return any.length > 1 ? any : NONE
}

/** Filter of features by id (stretch directions hovered or pinned on the map). */
export const idsFilter = (ids) => (ids && ids.length ? ['in', ['get', 'id'], ['literal', [...new Set(ids)].sort()]] : NONE)

/**
 * line-opacity for a focus. `classes`: Set of emphasised class indices (legend hover / pin); `match`: a filter of
 * emphasised features (table hover / pin), or null. With neither, everything is at BASE_OPACITY.
 */
export function opacityExpression(band = DEFAULT_BAND, { classes = null, match = null } = {}) {
  const byClass = classes && classes.size
  if (!byClass && !match) return BASE_OPACITY
  let strong = null
  if (byClass) {
    const e = ['step', ['get', props(band).v], classes.has(0) ? 1 : 0]
    CLASS_BREAKS.forEach((b, i) => e.push(b, classes.has(i + 1) ? 1 : 0))
    strong = ['==', e, 1]
  }
  if (match) strong = strong ? ['any', strong, match] : match
  return ['case', strong, BASE_OPACITY, DIM_OPACITY]
}

/**
 * MapLibre layers (without "source") of one "lines" catalog layer for the selected band, bottom to top: quiet
 * tier, busy tier (solid and dashed each), then the white highlight of hot stretches on top.
 * `hot` is a filter (linesFilter / idsFilter) or null.
 */
export function lineSpecs(layer, band = DEFAULT_BAND, hot = null) {
  const group = groupOf(layer)
  const z = MINZOOM[group] ?? 10
  const sl = layer.type === 'pmtiles' && layer.source_layer ? { 'source-layer': layer.source_layer } : {}
  const specs = []
  for (const tier of [...TIERS].reverse()) {
    for (const dashed of [false, true]) {
      specs.push({
        id: lineId(layer, tier, dashed), type: 'line', ...sl,
        minzoom: tier === 'busy' ? z : z + QUIET_DELAY,
        filter: tierFilter(band, tier, dashed),
        layout: { 'line-cap': dashed ? 'butt' : 'round', 'line-join': 'round' },
        paint: {
          'line-color': colorExpression(band), 'line-width': widthExpression(band),
          'line-offset': offsetExpression(band, group), 'line-opacity': BASE_OPACITY,
          ...(dashed ? { 'line-dasharray': [1.6, 1.2] } : {}),
        },
      })
    }
  }
  specs.push({
    id: hotLineId(layer), type: 'line', ...sl, minzoom: z, filter: hot || NONE,
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': HOT_COLOR, 'line-gap-width': widthExpression(band), 'line-width': 1.4,
      'line-offset': offsetExpression(band, group), 'line-opacity': 0.95,
    },
  })
  return specs
}

/** Ids of the coloured layers (for queryRenderedFeatures), without the highlight. */
export const lineLayerIds = (layer) => TIERS.flatMap((t) => [lineId(layer, t, false), lineId(layer, t, true)])

/** Applies a band, a focus and a highlight to the layers that exist on the map; cheap, no restacking. */
export function applyLines(map, layer, band, { classes = null, match = null, hot = null } = {}) {
  const op = opacityExpression(band, { classes, match })
  for (const tier of TIERS) {
    for (const dashed of [false, true]) {
      const id = lineId(layer, tier, dashed)
      if (!map.getLayer(id)) continue
      map.setFilter(id, tierFilter(band, tier, dashed))
      map.setPaintProperty(id, 'line-color', colorExpression(band))
      map.setPaintProperty(id, 'line-width', widthExpression(band))
      map.setPaintProperty(id, 'line-offset', offsetExpression(band, groupOf(layer)))
      map.setPaintProperty(id, 'line-opacity', op)
    }
  }
  if (map.getLayer(hotLineId(layer))) {
    map.setFilter(hotLineId(layer), hot || NONE)
    map.setPaintProperty(hotLineId(layer), 'line-gap-width', widthExpression(band))
    map.setPaintProperty(hotLineId(layer), 'line-offset', offsetExpression(band, groupOf(layer)))
  }
}

/**
 * What the pointer is on: the topmost feature of this layer in `features` (as queryRenderedFeatures returns them,
 * top first). {id, cls, keys, properties} or null; `cls` is the class index in the band, `keys` the line-table rows.
 */
export function hitTest(layer, features, band = DEFAULT_BAND) {
  const ids = new Set(lineLayerIds(layer))
  const f = (features || []).find((x) => ids.has(x?.layer?.id))
  if (!f) return null
  const p = f.properties || {}
  return { id: p.id, cls: classOf(p[props(band).v]), keys: featureLineKeys(p), properties: p }
}

/** The pixel box around a point used for hit testing: thin lines are hard to hit with a finger. */
export const hitBox = (point, pad = 4) => [[point.x - pad, point.y - pad], [point.x + pad, point.y + pad]]
