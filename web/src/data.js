import { DATA_BASE_URL, DATA_FILES } from './config'

async function getJson(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`)
  // a dev server answers a missing file with the page itself
  try { return await res.json() } catch { throw new Error(`${url}: to nie jest JSON`) }
}

/** The catalog is required: without it there is nothing to show. */
export async function loadCatalog() {
  const c = await getJson(DATA_BASE_URL + DATA_FILES.catalog)
  return { generated: c.generated, agglomerations: c.agglomerations || [], layers: c.layers || [] }
}

/** Metrics may be absent or empty at first; that is not an error. */
export async function loadMetrics() {
  try {
    const m = await getJson(DATA_BASE_URL + DATA_FILES.metrics)
    return { generated: m.generated, metrics: Array.isArray(m.metrics) ? m.metrics : [] }
  } catch {
    return { generated: null, metrics: [] }
  }
}

/** The list of GTFS publishers; optional, the page works without it. */
export async function loadAttributions() {
  try {
    const a = await getJson(DATA_BASE_URL + DATA_FILES.attributions)
    return { gtfs_feeds: Array.isArray(a.gtfs_feeds) ? a.gtfs_feeds : [] }
  } catch {
    return { gtfs_feeds: [] }
  }
}

/** Colour of a layer's checkbox in the sidebar. */
export function layerColor(layer) {
  if (layer.kind === 'boundary') return '#1D4ED8'
  if (layer.kind === 'mask') return '#8A8A84'
  const colors = layer.ramp?.colors
  return colors ? colors[Math.min(colors.length - 1, Math.floor(colors.length * 0.7))] : '#1D4ED8'
}

/** Layers listed as available and not yet available. */
export const isReady = (l) => l.status === 'ready'
