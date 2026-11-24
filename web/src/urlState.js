// The view lives in the address, so a link opens on the same agglomeration and
// layers. Only what differs from the defaults is written.
//   #a=wroclaw&l=fua,density250&v=layer:variant&s=pwdens_census_1km:desc&sd=gini:asc&d=full
// l= lists the ids of the layers drawn (empty: none); old addresses that list several value layers or several
// layers of one overlay group still open, on the first of each (layerControl.stateFromIds).
// v= is the chosen variant of layers that have variants.
// s= and sd= are the sorts of the city comparison and of its density table: the metric whose row orders the city
// columns, and the way (desc / asc). Absent: the default order of the cities. Addresses without them still open.
// d= is the state of the bottom dock on desktop: folded, half or full. Absent (an old address): half.

import { activeIds, initialState, stateFromIds, variantsToWrite } from './layerControl'
import { DEFAULT_DOCK, parseDock } from './kitx/dock'

const LIST = ','
const DIRS = ['asc', 'desc']

/** "metric:dir" -> {key, dir}; anything else is no sort (undefined). */
export function parseSort(text) {
  if (!text) return undefined
  const i = text.lastIndexOf(':')
  const key = i > 0 ? text.slice(0, i) : ''
  const dir = text.slice(i + 1)
  return key && DIRS.includes(dir) ? { key, dir } : undefined
}

/** {key, dir} -> "metric:dir"; '' for none. */
export const sortText = (sort) => (sort && sort.key && DIRS.includes(sort.dir) ? `${sort.key}:${sort.dir}` : '')

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
    sort: parseSort(q.get('s')),
    sortDensity: parseSort(q.get('sd')),
    dock: parseDock(q.get('d')),
  }
}

const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x))

/** The hash (with '#', or '' when plain) for a state, given the defaults. `variants` is {layerId: key}. */
export function hashOf({ agg, layers, variants = {}, sort, sortDensity, dock }, defaults) {
  const q = new URLSearchParams()
  if (agg) q.set('a', agg)
  const on = [...layers].sort()
  if (!sameSet(on, [...defaults.layers])) q.set('l', on.join(LIST))
  const v = Object.entries(variants).map(([id, k]) => `${id}:${k}`).sort()
  if (v.length) q.set('v', v.join(LIST))
  if (sortText(sort)) q.set('s', sortText(sort))
  if (sortText(sortDensity)) q.set('sd', sortText(sortDensity))
  if (dock && dock !== DEFAULT_DOCK && parseDock(dock)) q.set('d', dock)
  // ',' and ':' are fine in a fragment; left unescaped the link stays readable
  const s = q.toString().replace(/%2C/g, ',').replace(/%3A/g, ':')
  return s ? `#${s}` : ''
}

/** The hash of the page state: `view` is the layer-control state (layerControl.js), `sorts` is {sort, sortDensity, dock}. */
export function hashOfView(agg, view, layers, sorts = {}) {
  const defaults = { layers: [...activeIds(initialState(layers), layers)] }
  const active = activeIds(view, layers)
  return hashOf({ agg, layers: [...active], variants: variantsToWrite(view, layers, active), sort: sorts.sort, sortDensity: sorts.sortDensity, dock: sorts.dock }, defaults)
}

/**
 * Checks a parsed hash against the catalog; anything unknown falls back. Returns {agg, state, sort, sortDensity, dock}; the
 * sorts are {key, dir} or null, the dock is a state (an old address without one gets the half state). Their keys are not checked here: a table ignores a key it has no row for.
 */
export function resolveHash(parsed, { agglomerations, layers }) {
  const agg = agglomerations.some((a) => a.id === parsed.agg) ? parsed.agg : null
  const state = parsed.layers ? stateFromIds(parsed.layers, layers, parsed.variants) : initialState(layers)
  return { agg, state, sort: parsed.sort ?? null, sortDensity: parsed.sortDensity ?? null, dock: parsed.dock ?? DEFAULT_DOCK }
}
