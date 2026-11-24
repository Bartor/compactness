// Which layers are on. Layers of the same exclusive group share the map area, so at most one of each group
// is on: value layers (choropleths, drawn at 0.8 opacity, unreadable when stacked) form one group, point
// layers (stop areas) another. The groups do not exclude each other, so a points layer can sit on a value
// layer. Boundaries and masks are independent of all of it.

const GROUP_OF_KIND = { choropleth: 'values', points: 'points' }

/** The exclusive group of a layer id ('values', 'points') or null. */
export const groupOf = (layers, id) => GROUP_OF_KIND[layers.find((l) => l.id === id)?.kind] ?? null

/** The set of active ids after switching `id` on or off; switching a layer on switches off the others of its group. */
export function toggleLayer(active, id, on, layers) {
  const next = new Set(active)
  if (!on) {
    next.delete(id)
    return next
  }
  const g = groupOf(layers, id)
  if (g) for (const other of [...next]) if (groupOf(layers, other) === g) next.delete(other)
  next.add(id)
  return next
}

/** A list of ids (e.g. from an address) reduced to at most one layer per exclusive group, the first listed. */
export function oneOfEachGroup(ids, layers) {
  const seen = new Set()
  return ids.filter((id) => {
    const g = groupOf(layers, id)
    if (!g) return true
    if (seen.has(g)) return false
    seen.add(g)
    return true
  })
}

/** Kept for callers of the old name. */
export const oneChoropleth = oneOfEachGroup
