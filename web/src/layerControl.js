// Which layers are on, as the sidebar controls model it.
//
//   value      id of the one grid value layer shown (kind "choropleth"), or null: "Tylko granice". Value layers
//              colour the whole area, so they are a radio choice and never stack.
//   overlays   one entry per overlay group, {on, layer}: a group is a catalog `kind` listed in OVERLAY_KINDS.
//              Overlays are independent switches that can be combined with any value layer. A group with several
//              layers of its kind chooses which one is drawn (`layer`); at most one layer of a group is drawn.
//   variants   {layerId: key}: the chosen variant of a layer that offers some (`layer.variants`, a list of
//              {key, label}, for example time bands). Missing = the layer's first variant.
//
// The map and the legends still work on a plain set of layer ids: activeIds() derives it.
// To add an overlay kind (for example "lines" for timetable speeds), add it to OVERLAY_KINDS and teach
// mapLayers.js how to draw it; the sidebar, the address and this module need nothing else. Kinds that are not
// listed here are ignored wherever they turn up in the catalog.

export const OVERLAY_KINDS = {
  boundary: { label: 'Granice miast', order: 0, defaultOn: true },
  // the hatch of "brak danych o rozkładach" is drawn by every layer that can have such cells (it comes in their tiles), so
  // it is not a switch of its own: the catalog's mask layer is left out of the controls (old addresses naming it are ignored)
  points: { label: 'Węzły przesiadkowe', order: 2 },
}

export const VALUE_KIND = 'choropleth'

const ready = (l) => l && l.status === 'ready'

/** Ready grid value layers, in catalog order. */
export const valueLayers = (layers) => layers.filter((l) => ready(l) && l.kind === VALUE_KIND)

/** The overlay groups the catalog can fill: [{kind, label, layers}] in display order, only non-empty ones. */
export function overlayGroups(layers) {
  return Object.entries(OVERLAY_KINDS)
    .sort(([, a], [, b]) => a.order - b.order)
    .map(([kind, def]) => ({ kind, label: def.label, layers: layers.filter((l) => ready(l) && l.kind === kind) }))
    .filter((g) => g.layers.length > 0)
}

/** The default variant key of a layer, or null when it has none. */
export const defaultVariant = (layer) => (Array.isArray(layer?.variants) && layer.variants.length ? layer.variants[0].key : null)

/** The variant of `layer` in force: the chosen one when the layer still offers it, else the first. */
export function variantOf(state, layer) {
  const keys = (layer?.variants || []).map((v) => v.key)
  const k = state.variants?.[layer?.id]
  return k != null && keys.includes(k) ? k : defaultVariant(layer)
}

function emptyOverlays(layers, on) {
  const out = {}
  for (const g of overlayGroups(layers)) out[g.kind] = { on: on && !!OVERLAY_KINDS[g.kind].defaultOn, layer: g.layers[0].id }
  return out
}

/** What the page shows when the address says nothing: outlines only. */
export const initialState = (layers) => ({ value: null, overlays: emptyOverlays(layers, true), variants: {} })

/** The set of layer ids to draw. */
export function activeIds(state, layers) {
  const ids = new Set()
  if (state.value && valueLayers(layers).some((l) => l.id === state.value)) ids.add(state.value)
  for (const g of overlayGroups(layers)) {
    const o = state.overlays[g.kind]
    if (o?.on && g.layers.some((l) => l.id === o.layer)) ids.add(o.layer)
  }
  return ids
}

/** Chooses the value layer (null: none). An unknown id leaves the state alone. */
export function setValue(state, id, layers) {
  if (id != null && !valueLayers(layers).some((l) => l.id === id)) return state
  return state.value === id ? state : { ...state, value: id }
}

/** Switches an overlay group on or off. */
export function setOverlayOn(state, kind, on) {
  const o = state.overlays[kind]
  if (!o || o.on === on) return state
  return { ...state, overlays: { ...state.overlays, [kind]: { ...o, on } } }
}

/** Chooses which layer of a group is drawn when the group is on. */
export function chooseOverlay(state, kind, id, layers) {
  const g = overlayGroups(layers).find((x) => x.kind === kind)
  const o = state.overlays[kind]
  if (!g || !o || !g.layers.some((l) => l.id === id) || o.layer === id) return state
  return { ...state, overlays: { ...state.overlays, [kind]: { ...o, layer: id } } }
}

/** Chooses a variant of a layer; a key the layer does not offer is ignored. */
export function setVariant(state, layer, key) {
  if (!layer || !(layer.variants || []).some((v) => v.key === key) || state.variants?.[layer.id] === key) return state
  return { ...state, variants: { ...state.variants, [layer.id]: key } }
}

/** Shows a layer whatever it is: a value layer becomes the chosen one, an overlay is switched on and chosen. */
export function revealLayer(state, layers, id) {
  const l = layers.find((x) => x.id === id && ready(x))
  if (!l) return state
  if (l.kind === VALUE_KIND) return setValue(state, id, layers)
  if (!OVERLAY_KINDS[l.kind]) return state
  return setOverlayOn(chooseOverlay(state, l.kind, id, layers), l.kind, true)
}

/**
 * The state for a list of layer ids, as an address (or an old address) gives them. Everything not listed is
 * off: an address with `l=` empty shows no layers at all. Ids that are unknown, not ready or of an unlisted
 * kind are dropped; of several value layers, or several layers of one overlay group, the first listed wins.
 * `variants` is {layerId: key}.
 */
export function stateFromIds(ids, layers, variants = {}) {
  let state = { value: null, overlays: emptyOverlays(layers, false), variants: {} }
  let valueSet = false
  for (const id of ids) {
    const l = layers.find((x) => x.id === id && ready(x))
    if (!l) continue
    if (l.kind === VALUE_KIND) {
      if (!valueSet) { state = setValue(state, id, layers); valueSet = true }
    } else if (OVERLAY_KINDS[l.kind] && !state.overlays[l.kind]?.on) {
      state = setOverlayOn(chooseOverlay(state, l.kind, id, layers), l.kind, true)
    }
  }
  for (const [id, key] of Object.entries(variants)) {
    state = setVariant(state, layers.find((x) => x.id === id), key)
  }
  return state
}

/** {layerId: key} of the chosen variants that differ from a layer's first one, for the active layers only. */
export function variantsToWrite(state, layers, active) {
  const out = {}
  for (const l of layers) {
    if (!active.has(l.id)) continue
    const k = variantOf(state, l)
    if (k != null && k !== defaultVariant(l)) out[l.id] = k
  }
  return out
}

/** A short label for a layer in a chooser: the part of the title after "Something: ", unless the catalog gives `chip`. */
export function chipLabel(layer) {
  if (layer.chip) return layer.chip
  const i = layer.title.indexOf(': ')
  return i > 0 ? layer.title.slice(i + 2) : layer.title
}
