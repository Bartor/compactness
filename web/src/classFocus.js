// Linked highlighting of colour classes between a legend and what it explains (the map today, charts later).
// Hovering a class anywhere highlights it everywhere; a click pins it, and several classes can be pinned.
// State: {layerId, hover, from, pinned}; `hover` is a class index or null, `from` says where the pointer is
// ('legend' or 'map'), `pinned` is a sorted list of class indices.  Pointing at a legend row or pinning fades
// the other classes on the map; pointing at the map only marks the legend row, so the map does not flicker
// under a moving pointer.
// Every function returns the same object when nothing changes, so it can be used directly as a state updater.

export const EMPTY_FOCUS = Object.freeze({ layerId: null, hover: null, from: null, pinned: Object.freeze([]) })

/**
 * Pointer is over class `index` of `layerId` (index null: over none), in the legend or on the map.
 * Another layer starts from scratch.
 */
export function hoverClass(focus, layerId, index, from = 'legend') {
  if (index == null) {
    // leaving: only the layer that holds the hover (or an unspecified one) can clear it
    const mine = layerId == null || focus.layerId === layerId
    return !mine || focus.hover == null ? focus : { ...focus, hover: null, from: null }
  }
  if (layerId == null) return focus
  if (focus.layerId !== layerId) return { layerId, hover: index, from, pinned: [] }
  return focus.hover === index && focus.from === from ? focus : { ...focus, hover: index, from }
}

/** Click on class `index`: pin it, or unpin it when it was pinned. */
export function togglePinned(focus, layerId, index) {
  const same = focus.layerId === layerId
  const old = same ? focus.pinned : []
  const pinned = old.includes(index) ? old.filter((i) => i !== index) : [...old, index].sort((a, b) => a - b)
  return { layerId, hover: same ? focus.hover : null, from: same ? focus.from : null, pinned }
}

/** Unpin everything of a layer. */
export function clearPinned(focus, layerId) {
  if (focus.layerId !== layerId || !focus.pinned.length) return focus
  return { ...focus, pinned: [] }
}

/** Forget the focus when its layer is no longer shown. `visibleIds` is a Set. */
export function pruneFocus(focus, visibleIds) {
  return focus.layerId == null || visibleIds.has(focus.layerId) ? focus : EMPTY_FOCUS
}

/**
 * Class indices of `layerId` to draw at full strength: pinned, plus the one pointed at in the legend.
 * Empty = no emphasis.
 */
export function emphasised(focus, layerId) {
  if (focus.layerId !== layerId) return new Set()
  const s = new Set(focus.pinned)
  if (focus.hover != null && focus.from === 'legend') s.add(focus.hover)
  return s
}

/** The class of `layerId` under the pointer, wherever the pointer is; null when none. */
export const hovered = (focus, layerId) => (focus.layerId === layerId ? focus.hover : null)
