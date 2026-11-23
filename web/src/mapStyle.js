// Our own minimal basemap style on OpenFreeMap's vector tiles (OpenMapTiles
// schema, no key). Calm: warm grey land, pale blue water, white streets,
// muted labels, faint railways. Overlay layers are inserted before
// ANCHOR_LABELS so that names stay readable on top of them.
export const TILEJSON_URL = 'https://tiles.openfreemap.org/planet'
export const GLYPHS_URL = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf'
export const ANCHOR_LABELS = 'label-water'

const LAND = '#ECE9E2'
const WATER = '#C9D6E0'
const GREEN = '#E1E4D6'
const INK = '#6F6B63'
const FONT = ['Noto Sans Regular']
const FONT_BOLD = ['Noto Sans Bold']
const FONT_ITALIC = ['Noto Sans Italic']
const name = ['coalesce', ['get', 'name:pl'], ['get', 'name']]

const width = (...stops) => ['interpolate', ['exponential', 1.4], ['zoom'], ...stops]
const road = (classes) => ['all', ['in', ['get', 'class'], ['literal', classes]], ['!=', ['get', 'brunnel'], 'tunnel']]

const MAJOR = ['motorway', 'trunk', 'primary']
const MID = ['secondary', 'tertiary']
const MINOR = ['minor', 'service', 'track']

export function buildStyle() {
  return {
    version: 8,
    glyphs: GLYPHS_URL,
    sources: {
      openmaptiles: { type: 'vector', url: TILEJSON_URL },
    },
    layers: [
      { id: 'land', type: 'background', paint: { 'background-color': LAND } },
      {
        id: 'landcover', type: 'fill', source: 'openmaptiles', 'source-layer': 'landcover',
        filter: ['in', ['get', 'class'], ['literal', ['grass', 'wood', 'farmland']]],
        paint: { 'fill-color': GREEN, 'fill-opacity': 0.55 },
      },
      {
        id: 'park', type: 'fill', source: 'openmaptiles', 'source-layer': 'park',
        paint: { 'fill-color': GREEN, 'fill-opacity': 0.8 },
      },
      {
        id: 'water', type: 'fill', source: 'openmaptiles', 'source-layer': 'water',
        paint: { 'fill-color': WATER },
      },
      {
        id: 'waterway', type: 'line', source: 'openmaptiles', 'source-layer': 'waterway', minzoom: 8,
        paint: { 'line-color': WATER, 'line-width': width(8, 0.5, 14, 2.5) },
      },
      {
        id: 'building', type: 'fill', source: 'openmaptiles', 'source-layer': 'building', minzoom: 14,
        paint: { 'fill-color': '#E3DFD6', 'fill-opacity': 0.8 },
      },
      {
        id: 'road-casing', type: 'line', source: 'openmaptiles', 'source-layer': 'transportation', minzoom: 6,
        filter: road([...MAJOR, ...MID]),
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#D8D3C8',
          'line-width': width(6, 0.8, 10, 2, 14, 5, 18, 16),
        },
      },
      {
        id: 'road-minor', type: 'line', source: 'openmaptiles', 'source-layer': 'transportation', minzoom: 12,
        filter: road(MINOR),
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#FFFFFF', 'line-width': width(12, 0.4, 14, 1.2, 18, 8) },
      },
      {
        id: 'road-mid', type: 'line', source: 'openmaptiles', 'source-layer': 'transportation', minzoom: 8,
        filter: road(MID),
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#FFFFFF', 'line-width': width(8, 0.4, 12, 1.2, 14, 3, 18, 12) },
      },
      {
        id: 'road-major', type: 'line', source: 'openmaptiles', 'source-layer': 'transportation', minzoom: 5,
        filter: road(MAJOR),
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#FFFFFF', 'line-width': width(5, 0.5, 10, 1.4, 14, 3.5, 18, 13) },
      },
      {
        id: 'rail', type: 'line', source: 'openmaptiles', 'source-layer': 'transportation', minzoom: 8,
        filter: ['all', ['==', ['get', 'class'], 'rail'], ['!=', ['get', 'brunnel'], 'tunnel']],
        paint: { 'line-color': '#B3AFA5', 'line-width': width(8, 0.4, 14, 1.2, 18, 2.4), 'line-opacity': 0.9 },
      },
      {
        id: 'rail-ties', type: 'line', source: 'openmaptiles', 'source-layer': 'transportation', minzoom: 14,
        filter: ['all', ['==', ['get', 'class'], 'rail'], ['!=', ['get', 'brunnel'], 'tunnel']],
        paint: { 'line-color': LAND, 'line-width': width(14, 0.6, 18, 1.4), 'line-dasharray': [3, 3] },
      },
      {
        id: 'boundary-country', type: 'line', source: 'openmaptiles', 'source-layer': 'boundary',
        filter: ['<=', ['get', 'admin_level'], 2],
        paint: { 'line-color': '#A8A398', 'line-width': width(2, 0.6, 10, 1.4), 'line-dasharray': [4, 2] },
      },
      // ---- overlay layers of the catalog are inserted here, below the labels ----
      {
        id: ANCHOR_LABELS, type: 'symbol', source: 'openmaptiles', 'source-layer': 'water_name', minzoom: 6,
        layout: { 'text-field': name, 'text-font': FONT_ITALIC, 'text-size': 11, 'text-letter-spacing': 0.1 },
        paint: { 'text-color': '#7F93A3', 'text-halo-color': WATER, 'text-halo-width': 1 },
      },
      {
        id: 'label-street', type: 'symbol', source: 'openmaptiles', 'source-layer': 'transportation_name', minzoom: 14,
        layout: {
          'text-field': name, 'text-font': FONT, 'text-size': 11,
          'symbol-placement': 'line', 'text-rotation-alignment': 'map',
        },
        paint: { 'text-color': '#8D897F', 'text-halo-color': '#FFFFFF', 'text-halo-width': 1.2 },
      },
      {
        id: 'label-village', type: 'symbol', source: 'openmaptiles', 'source-layer': 'place', minzoom: 10,
        filter: ['in', ['get', 'class'], ['literal', ['village', 'suburb', 'neighbourhood', 'hamlet']]],
        layout: { 'text-field': name, 'text-font': FONT, 'text-size': 11, 'text-max-width': 8 },
        paint: { 'text-color': '#8D897F', 'text-halo-color': LAND, 'text-halo-width': 1.2 },
      },
      {
        id: 'label-town', type: 'symbol', source: 'openmaptiles', 'source-layer': 'place', minzoom: 7,
        filter: ['==', ['get', 'class'], 'town'],
        layout: { 'text-field': name, 'text-font': FONT, 'text-size': 12, 'text-max-width': 8 },
        paint: { 'text-color': INK, 'text-halo-color': LAND, 'text-halo-width': 1.4 },
      },
      {
        id: 'label-city', type: 'symbol', source: 'openmaptiles', 'source-layer': 'place', minzoom: 3,
        filter: ['==', ['get', 'class'], 'city'],
        layout: {
          'text-field': name, 'text-font': FONT_BOLD,
          'text-size': ['interpolate', ['linear'], ['zoom'], 4, 11, 10, 16],
          'text-max-width': 8,
        },
        paint: { 'text-color': '#4F4B44', 'text-halo-color': LAND, 'text-halo-width': 1.6 },
      },
      {
        id: 'label-country', type: 'symbol', source: 'openmaptiles', 'source-layer': 'place', minzoom: 2, maxzoom: 7,
        filter: ['==', ['get', 'class'], 'country'],
        layout: { 'text-field': name, 'text-font': FONT_BOLD, 'text-size': 12, 'text-transform': 'uppercase', 'text-letter-spacing': 0.15 },
        paint: { 'text-color': '#8D897F', 'text-halo-color': LAND, 'text-halo-width': 1.4 },
      },
    ],
  }
}

/** A diagonal hatch for "brak danych": a grey wash with darker stripes, RGBA bytes. */
export function hatchImage(size = 12) {
  const data = new Uint8Array(size * size * 4)
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4
      const stripe = (x + y) % 6 < 2
      const [r, g, b, a] = stripe ? [110, 110, 106, 190] : [200, 198, 192, 70]
      data[i] = r; data[i + 1] = g; data[i + 2] = b; data[i + 3] = a
    }
  }
  return { width: size, height: size, data }
}
