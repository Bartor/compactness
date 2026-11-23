// The only place that knows where data and tiles live. Both bases are relative
// to the page; to serve tiles from another host later, change TILES_BASE_URL
// (an absolute https:// URL works) and nothing else.
export const DATA_BASE_URL = './data/'
export const TILES_BASE_URL = './tiles/'

export const DATA_FILES = { catalog: 'catalog.json', metrics: 'metrics.json', attributions: 'attributions.json' }

/** Public-transport accent. */
export const ACCENT = '#1D4ED8'

/**
 * Where a catalog URL really is. The catalog speaks in repo-relative paths
 * ("data/fua.geojson", "tiles/x.pmtiles"); the prefix is swapped for the
 * configured base. Absolute URLs pass through.
 */
export function resolveUrl(url, dataBase = DATA_BASE_URL, tilesBase = TILES_BASE_URL) {
  if (!url) return url
  if (/^[a-z][a-z0-9+.-]*:/i.test(url) || url.startsWith('//')) return url
  const path = url.replace(/^\.?\//, '')
  if (path.startsWith('data/')) return dataBase + path.slice(5)
  if (path.startsWith('tiles/')) return tilesBase + path.slice(6)
  return path
}

/** The same, made absolute: MapLibre's workers have no page to resolve against. */
export function absoluteUrl(url, base = typeof document !== 'undefined' ? document.baseURI : 'http://localhost/') {
  return new URL(resolveUrl(url), base).href
}
