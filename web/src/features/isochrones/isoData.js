// Loading the per-agglomeration isochrone files (results/web/isochrones/<agg>.json, served as
// data/isochrones/<agg>.json). One file per city, fetched on first use and kept for the session.
import { DATA_BASE_URL } from '../../config'

export const ISO_DIR = 'isochrones/'
export const isoUrl = (agg, base = DATA_BASE_URL) => `${base}${ISO_DIR}${agg}.json`

const cache = new Map()

/** Basic shape check; a file that fails it is treated as missing. */
export function validIsoFile(f) {
  return !!f && typeof f === 'object' && Array.isArray(f.origins) && f.iso && typeof f.iso === 'object'
    && f.scenarios && typeof f.scenarios === 'object'
}

/**
 * The isochrone file of one agglomeration, or null when it is absent (cities without a file simply have no
 * "skąd dojadę" mode). `fetchImpl` is for tests.
 */
export function loadIsochrones(agg, { base = DATA_BASE_URL, fetchImpl = globalThis.fetch } = {}) {
  if (!agg) return Promise.resolve(null)
  const key = isoUrl(agg, base)
  if (!cache.has(key)) {
    const p = (async () => {
      try {
        const res = await fetchImpl(key)
        if (!res.ok) return null
        const f = await res.json()
        return validIsoFile(f) ? f : null
      } catch {
        return null
      }
    })()
    cache.set(key, p)
    // a failed load may succeed later (network): do not keep the null
    p.then((v) => { if (v === null) cache.delete(key) })
  }
  return cache.get(key)
}

export const clearIsoCache = () => cache.clear()
