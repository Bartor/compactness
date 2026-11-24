// Pure logic of the "skąd dojadę" mode: decoding the precomputed isochrone file (pipeline/isochrones.py), finding the
// precomputed origin nearest to a click, building GeoJSON for MapLibre and the numbers of the card. No React, no map.

/** Bands drawn per scenario, in minutes; the file says the same in `scenarios[s].minutes`. */
export const TRANSIT_MINUTES = [15, 30, 45, 60]
export const WALK_MINUTES = [15, 30]
export const SCENARIOS = ['am', 'evening', 'walk']
export const SCENARIO_LABEL = {
  am: 'rano (środa 7–9)',
  evening: 'wieczorem (środa 20–22)',
  walk: 'tylko pieszo',
}
export const KIND_LABEL = { hub: 'węzeł', centre: 'centrum', stop_area: 'zespół przystanków', grid: 'punkt siatki' }

export const bandLabel = (min) => `do ${min} min`

/**
 * Google encoded polyline, precision 5 -> [[lon, lat], ...] (GeoJSON order; the format itself stores lat first).
 * The ring is returned closed (first point repeated at the end), as GeoJSON wants.
 */
export function decodeRing(s) {
  const out = []
  let i = 0
  let lat = 0
  let lon = 0
  while (i < s.length) {
    const vals = []
    for (let k = 0; k < 2; k++) {
      let shift = 0
      let res = 0
      let b
      do {
        b = s.charCodeAt(i++) - 63
        res |= (b & 0x1f) << shift
        shift += 5
      } while (b >= 0x20)
      vals.push(res & 1 ? ~(res >> 1) : res >> 1)
    }
    lat += vals[0]
    lon += vals[1]
    out.push([lon / 1e5, lat / 1e5])
  }
  if (out.length && (out[0][0] !== out[out.length - 1][0] || out[0][1] !== out[out.length - 1][1])) out.push(out[0].slice())
  return out
}

/** One band's encoded polygons ([[outer, hole, ...], ...]) -> MultiPolygon coordinates. */
export const decodePolygons = (enc) => (enc || []).map((rings) => rings.map(decodeRing))

/** Distance in metres between two [lon, lat] points (equirectangular; fine at city scale). */
export function distanceM(a, b) {
  const R = 6371008.8
  const rad = Math.PI / 180
  const x = (b[0] - a[0]) * rad * Math.cos(((a[1] + b[1]) / 2) * rad)
  const y = (b[1] - a[1]) * rad
  return Math.hypot(x, y) * R
}

/**
 * The precomputed origin nearest to a point: {origin, distanceM} or null when the index is empty.
 * Ties go to the earlier origin in the file (hubs and centres come first there).
 */
export function nearestOrigin(origins, lngLat) {
  let best = null
  for (const o of origins || []) {
    const d = distanceM([o.lon, o.lat], lngLat)
    if (!best || d < best.distanceM) best = { origin: o, distanceM: d }
  }
  return best
}

/**
 * GeoJSON of one origin and scenario: one MultiPolygon feature per band, largest first (drawing order), with
 * minutes, label ("do 30 min"), residents (cumulative) and residents_band. Null when the origin or scenario is
 * missing. The polygons are cumulative: "do 30 min" contains "do 15 min".
 */
export function isoGeoJSON(file, originId, scenario) {
  const rec = file?.iso?.[originId]?.[scenario]
  if (!rec) return null
  const minutes = file.scenarios?.[scenario]?.minutes || (scenario === 'walk' ? WALK_MINUTES : TRANSIT_MINUTES)
  const features = minutes.map((min, i) => ({
    type: 'Feature',
    properties: {
      scenario, minutes: min, label: bandLabel(min),
      residents: rec.residents?.[i] ?? null, residents_band: rec.residents_band?.[i] ?? null,
    },
    geometry: { type: 'MultiPolygon', coordinates: decodePolygons(rec.geom?.[i]) },
  }))
  return { type: 'FeatureCollection', features: features.reverse() }
}

/** The origin as a GeoJSON point (for the marker and its name). */
export function originGeoJSON(origin) {
  if (!origin) return null
  return {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { id: origin.id, name: origin.name, kind: origin.kind },
      geometry: { type: 'Point', coordinates: [origin.lon, origin.lat] },
    }],
  }
}

/** Residents in Polish: "–" for missing, exact below 1 000, "12,3 tys." below 100 000, "254 tys.", "1,25 mln". */
export function formatResidents(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return '–'
  const f = (v, d) => v.toLocaleString('pl-PL', { minimumFractionDigits: d, maximumFractionDigits: d })
  if (n < 1000) return f(Math.round(n), 0)
  if (n < 100000) return `${f(n / 1000, 1)} tys.`
  if (n < 1000000) return `${f(Math.round(n / 1000), 0)} tys.`
  return `${f(n / 1e6, 2)} mln`
}

export function formatDistance(m) {
  if (m === null || m === undefined) return '–'
  if (m < 1000) return `${Math.round(m / 10) * 10} m`
  return `${(m / 1000).toLocaleString('pl-PL', { maximumFractionDigits: 1 })} km`
}

/**
 * Rows of the card: one per band in minutes (15, 30, 45, 60), cumulative residents for each scenario
 * (walk only for the bands it has; null elsewhere, shown as "–").
 */
export function cardRows(file, originId) {
  const rec = file?.iso?.[originId]
  if (!rec) return []
  const mins = file.scenarios?.am?.minutes || TRANSIT_MINUTES
  return mins.map((min) => {
    const row = { minutes: min, label: bandLabel(min) }
    for (const s of SCENARIOS) {
      const ms = file.scenarios?.[s]?.minutes || (s === 'walk' ? WALK_MINUTES : TRANSIT_MINUTES)
      const i = ms.indexOf(min)
      row[s] = i >= 0 ? rec[s]?.residents?.[i] ?? null : null
    }
    return row
  })
}
