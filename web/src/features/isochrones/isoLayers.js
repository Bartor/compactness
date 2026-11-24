// MapLibre sources and layers of the "skąd dojadę" mode. Pure specs plus syncIsochrones(), which puts the current
// isochrone (or nothing) on a live map. Colours are for the dark basemap: the shortest band is the strongest, the
// outer bands lighter and more transparent. Polygons are cumulative and drawn largest first, so the inner bands
// sit on top and their colour deepens where they overlap.

export const ISO_SOURCE = 'iso-src'
export const ISO_ORIGIN_SOURCE = 'iso-origin-src'
export const ISO_WALK_SOURCE = 'iso-walk-src'

/** Fill colour and opacity per band (minutes). */
export const BAND_STYLE = {
  15: { color: '#3FC1B0', opacity: 0.5 },
  30: { color: '#6CCFC1', opacity: 0.38 },
  45: { color: '#9BDDD3', opacity: 0.27 },
  60: { color: '#C9EEE8', opacity: 0.18 },
}
export const WALK_LINE = '#F1E7C9'
export const ORIGIN_COLOR = '#FFFFFF'

const byMinutes = (prop) => ['match', ['get', 'minutes'],
  ...Object.entries(BAND_STYLE).flatMap(([m, s]) => [Number(m), s[prop]]), BAND_STYLE[60][prop]]

/** Layer ids, bottom to top. */
export const ISO_LAYERS = {
  fill: 'iso:fill', line: 'iso:line', label: 'iso:label', walk: 'iso:walk', walkLabel: 'iso:walk-label',
  origin: 'iso:origin', originLabel: 'iso:origin-label',
}

/** MapLibre layer specs (with sources) in drawing order. Fonts are the basemap's glyphs. */
export function isoLayerSpecs() {
  return [
    {
      id: ISO_LAYERS.fill, type: 'fill', source: ISO_SOURCE,
      paint: { 'fill-color': byMinutes('color'), 'fill-opacity': byMinutes('opacity') },
    },
    {
      id: ISO_LAYERS.line, type: 'line', source: ISO_SOURCE,
      layout: { 'line-join': 'round' },
      paint: { 'line-color': byMinutes('color'), 'line-width': 1.1, 'line-opacity': 0.9 },
    },
    {
      id: ISO_LAYERS.label, type: 'symbol', source: ISO_SOURCE, minzoom: 9,
      layout: {
        'symbol-placement': 'line', 'text-field': ['get', 'label'], 'text-font': ['Noto Sans Regular'],
        'text-size': 11, 'symbol-spacing': 400, 'text-max-angle': 30,
      },
      paint: { 'text-color': byMinutes('color'), 'text-halo-color': '#12141a', 'text-halo-width': 1.4 },
    },
    {
      id: ISO_LAYERS.walk, type: 'line', source: ISO_WALK_SOURCE,
      layout: { 'line-join': 'round' },
      paint: { 'line-color': WALK_LINE, 'line-width': 1.4, 'line-dasharray': [2, 2], 'line-opacity': 0.9 },
    },
    {
      id: ISO_LAYERS.walkLabel, type: 'symbol', source: ISO_WALK_SOURCE, minzoom: 11,
      layout: {
        'symbol-placement': 'line', 'text-field': ['concat', 'pieszo ', ['get', 'label']],
        'text-font': ['Noto Sans Regular'], 'text-size': 10, 'symbol-spacing': 300,
      },
      paint: { 'text-color': WALK_LINE, 'text-halo-color': '#12141a', 'text-halo-width': 1.4 },
    },
    {
      id: ISO_LAYERS.origin, type: 'circle', source: ISO_ORIGIN_SOURCE,
      paint: {
        'circle-radius': 6, 'circle-color': '#12141a', 'circle-stroke-color': ORIGIN_COLOR, 'circle-stroke-width': 2.5,
      },
    },
    {
      id: ISO_LAYERS.originLabel, type: 'symbol', source: ISO_ORIGIN_SOURCE,
      layout: {
        'text-field': ['get', 'name'], 'text-font': ['Noto Sans Bold'], 'text-size': 12,
        'text-offset': [0, 1.2], 'text-anchor': 'top',
      },
      paint: { 'text-color': ORIGIN_COLOR, 'text-halo-color': '#12141a', 'text-halo-width': 1.6 },
    },
  ]
}

const EMPTY = { type: 'FeatureCollection', features: [] }

/**
 * Shows {bands, walk, origin} (GeoJSON FeatureCollections from isoModel, any of them null) on the map, or removes
 * everything when `iso` is null. `before` is the layer to insert below (the basemap labels, ANCHOR_LABELS);
 * with the city outlines drawn above (see README), pass the first outline layer id instead.
 */
export function syncIsochrones(map, iso, before = undefined) {
  const specs = isoLayerSpecs()
  if (!iso) {
    for (const s of specs.slice().reverse()) if (map.getLayer(s.id)) map.removeLayer(s.id)
    for (const src of [ISO_SOURCE, ISO_WALK_SOURCE, ISO_ORIGIN_SOURCE]) if (map.getSource(src)) map.removeSource(src)
    return false
  }
  const data = { [ISO_SOURCE]: iso.bands || EMPTY, [ISO_WALK_SOURCE]: iso.walk || EMPTY, [ISO_ORIGIN_SOURCE]: iso.origin || EMPTY }
  for (const [src, d] of Object.entries(data)) {
    if (map.getSource(src)) map.getSource(src).setData(d)
    else map.addSource(src, { type: 'geojson', data: d })
  }
  const beforeId = before && map.getLayer(before) ? before : undefined
  // add what is missing, then move all of them (in order) just below `before`: other code that restacks its own
  // layers below the labels would otherwise cover the bands
  for (const s of specs) {
    if (!map.getLayer(s.id)) map.addLayer(s, beforeId)
    else if (map.moveLayer) map.moveLayer(s.id, beforeId)
  }
  return true
}

/** Swatches for a legend or the card: [{minutes, label, color, opacity}]. */
export const bandLegend = (minutes = [15, 30, 45, 60]) =>
  minutes.map((m) => ({ minutes: m, label: `do ${m} min`, color: BAND_STYLE[m].color, opacity: BAND_STYLE[m].opacity }))
