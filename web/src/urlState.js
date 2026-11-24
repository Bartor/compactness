// The view lives in the address, so a link opens on the same agglomeration and
// layers. Only what differs from the defaults is written.
//   #a=wroclaw&l=fua,density250&v=layer:variant
// l= lists the ids of the layers drawn (empty: none); old addresses that list several value layers or several
// layers of one overlay group still open, on the first of each (layerControl.stateFromIds).
// v= is the chosen variant of layers that have variants.

import { activeIds, initialState, stateFromIds, variantsToWrite } from './layerControl'

const LIST = ','

/** What the address asks for; absent keys stay undefined. */
export function readHash(hash = typeof window !== 'undefined' ? window.location.hash : '') {
  const q = new URLSearchParams(hash.replace(/^#/, ''))
  const variants = {}
  for (const pair of (q.get('v') || '').split(LIST).filter(Boolean)) {
    const i = pair.indexOf(':')
    if (i > 0) variants[pair.slice(0, i)] = pair.slice(i + 1)
  }
  return {
    agg: q.get('a') || undefined,
    layers: q.has('l') ? q.get('l').split(LIST).filter(Boolean) : undefined,
    variants,
  }
}

const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x))

/** The hash (with '#', or '' when plain) for a state, given the defaults. `variants` is {layerId: key}. */
export function hashOf({ agg, layers, variants = {} }, defaults) {
  const q = new URLSearchParams()
  if (agg) q.set('a', agg)
  const on = [...layers].sort()
  if (!sameSet(on, [...defaults.layers])) q.set('l', on.join(LIST))
  const v = Object.entries(variants).map(([id, k]) => `${id}:${k}`).sort()
  if (v.length) q.set('v', v.join(LIST))
  // ',' and ':' are fine in a fragment; left unescaped the link stays readable
  const s = q.toString().replace(/%2C/g, ',').replace(/%3A/g, ':')
  return s ? `#${s}` : ''
}

/** The hash of the page state: `view` is the layer-control state (layerControl.js). */
export function hashOfView(agg, view, layers) {
  const defaults = { layers: [...activeIds(initialState(layers), layers)] }
  const active = activeIds(view, layers)
  return hashOf({ agg, layers: [...active], variants: variantsToWrite(view, layers, active) }, defaults)
}

/** Checks a parsed hash against the catalog; anything unknown falls back. Returns {agg, state}. */
export function resolveHash(parsed, { agglomerations, layers }) {
  const agg = agglomerations.some((a) => a.id === parsed.agg) ? parsed.agg : null
  const state = parsed.layers ? stateFromIds(parsed.layers, layers, parsed.variants) : initialState(layers)
  return { agg, state }
}
