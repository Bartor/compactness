// The view lives in the address, so a link opens on the same agglomeration and
// layers. Only what differs from the defaults is written.
//   #a=wroclaw&l=fua,density250      l= (empty) means "no layers"

import { oneChoropleth } from './layerState'

const LIST = ','

/** What the address asks for; absent keys stay undefined. */
export function readHash(hash = typeof window !== 'undefined' ? window.location.hash : '') {
  const q = new URLSearchParams(hash.replace(/^#/, ''))
  return {
    agg: q.get('a') || undefined,
    layers: q.has('l') ? q.get('l').split(LIST).filter(Boolean) : undefined,
  }
}

const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x))

/** The hash (with '#', or '' when plain) for a state, given the defaults. */
export function hashOf({ agg, layers }, defaults) {
  const q = new URLSearchParams()
  if (agg) q.set('a', agg)
  const on = [...layers].sort()
  if (!sameSet(on, [...defaults.layers])) q.set('l', on.join(LIST))
  // ',' is fine in a fragment; left unescaped the link stays readable
  const s = q.toString().replace(/%2C/g, ',')
  return s ? `#${s}` : ''
}

/** Checks a parsed hash against the catalog; anything unknown falls back. */
export function resolveHash(parsed, { agglomerations, layers }, defaultLayers) {
  const agg = agglomerations.some((a) => a.id === parsed.agg) ? parsed.agg : null
  const ready = new Set(layers.filter((l) => l.status === 'ready').map((l) => l.id))
  const on = parsed.layers ? parsed.layers.filter((id) => ready.has(id)) : defaultLayers
  return { agg, layers: oneChoropleth(on, layers) }
}
