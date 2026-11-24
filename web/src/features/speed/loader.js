// Loading the speed overlay's data. The catalog entries carry relative urls ("data/speed/trams.geojson"); the bus
// entry carries `url_template` with "{agg}" (one file per agglomeration). The caller passes its own url resolver
// (the app's absoluteUrl), so this folder imports nothing from the app.
import { parseLines } from './lineTable'

export const LINES_URL = 'data/speed/lines.json'

/** The GeoJSON url of a "lines" layer for the selected agglomeration; null when the layer needs a city and has none. */
export function layerUrl(layer, agg) {
  if (!layer) return null
  if (layer.url_template) {
    if (!agg || (Array.isArray(layer.cities) && !layer.cities.includes(agg))) return null
    return layer.url_template.replace('{agg}', agg)
  }
  return layer.url || null
}

/** A copy of the catalog layer with `url` resolved for the city (what mapLayers.sourceSpec expects), or null. */
export function resolvedLayer(layer, agg) {
  const url = layerUrl(layer, agg)
  return url ? { ...layer, url } : null
}

const cache = new Map()

/**
 * Fetches and parses lines.json once per url. `resolve` maps a relative url to an absolute one; `fetchImpl` is for
 * tests. Resolves to parseLines(...) or rejects with an Error whose message is Polish and plain.
 */
export function loadSpeedLines(resolve = (u) => u, fetchImpl = (u) => fetch(u), url = LINES_URL) {
  const abs = resolve(url)
  if (!cache.has(abs)) {
    const p = Promise.resolve(fetchImpl(abs))
      .then((r) => {
        if (!r.ok) throw new Error(`Nie udało się wczytać tabeli linii (${r.status}).`)
        return r.json()
      })
      .then(parseLines)
      .catch((e) => { cache.delete(abs); throw e })
    cache.set(abs, p)
  }
  return cache.get(abs)
}

/** Forgets loaded tables (tests). */
export const clearSpeedCache = () => cache.clear()
