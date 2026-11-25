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
    return { generated: m.generated, metrics: Array.isArray(m.metrics) ? m.metrics.map(plainUnit) : [] }
  } catch {
    return { generated: null, metrics: [] }
  }
}

// Units as the pipeline writes them, in the words a resident uses (the files keep the trade terms).
const UNIT_TEXT = { 'wozkm/mieszk./dobę': 'km/mieszk./dobę', 'min równoważnych': 'min jazdy' }
export const plainUnit = (row) => (row && UNIT_TEXT[row.unit] ? { ...row, unit: UNIT_TEXT[row.unit] } : row)

/** The list of GTFS publishers; optional, the page works without it. */
export async function loadAttributions() {
  try {
    const a = await getJson(DATA_BASE_URL + DATA_FILES.attributions)
    return { gtfs_feeds: Array.isArray(a.gtfs_feeds) ? a.gtfs_feeds : [] }
  } catch {
    return { gtfs_feeds: [] }
  }
}

/** Per-class shares of residents of the selected city; optional, absent until the pipeline writes it. */
export async function loadClassShares() {
  try {
    const s = await getJson(DATA_BASE_URL + DATA_FILES.classShares)
    return s && typeof s === 'object' && !Array.isArray(s) ? s : {}
  } catch {
    return {}
  }
}

/** Residents by density class per city (form.json, for the metric pages); optional: null when it is not there. */
export async function loadForm() {
  try {
    const f = await getJson(DATA_BASE_URL + DATA_FILES.form)
    return f && Array.isArray(f.cities) && Array.isArray(f.classes) ? f : null
  } catch {
    return null
  }
}

/** The colour from the middle of a ramp: the dot of a layer in the sidebar. */
export function rampMid(ramp) {
  const colors = ramp?.colors
  return colors?.length ? colors[Math.floor(colors.length / 2)] : undefined
}

/** Colour of a layer's dot in the sidebar. */
export function layerColor(layer) {
  if (layer.kind === 'boundary') return '#9DB8E8'
  if (layer.kind === 'mask') return '#8A909C'
  return rampMid(layer.ramp) || '#9DB8E8'
}

/** Layers listed as available and not yet available. */
export const isReady = (l) => l.status === 'ready'
