import { useEffect, useState } from 'react'
import { resolveUrl } from './config'
import { topNodes } from './metricTable'

const cache = new Map()   // url -> Promise of the feature list

/** The features of a points file, fetched once per URL. */
export function loadNodeFeatures(url) {
  if (!cache.has(url)) {
    const p = fetch(url)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((j) => (Array.isArray(j.features) ? j.features : []))
    p.catch(() => cache.delete(url))
    cache.set(url, p)
  }
  return cache.get(url)
}

/**
 * The busiest stop areas of an agglomeration, fetched only when one is selected and a points layer exists:
 * {layer, nodes: [topNodes()]} or null while loading, on failure, or when there is nothing to show.
 */
export function useCityNodes(layer, agg, n = 8) {
  const [state, setState] = useState(null)
  const url = layer?.url ? resolveUrl(layer.url) : null
  useEffect(() => {
    setState(null)
    if (!url || !agg) return undefined
    let dead = false
    loadNodeFeatures(url)
      .then((f) => { if (!dead) setState({ layer, nodes: topNodes(f, agg, n) }) })
      .catch(() => {})
    return () => { dead = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, agg, n])
  return state && state.nodes.length ? state : null
}
