// Which layers are on. Value layers (choropleths) share the map area and are drawn at 0.8 opacity,
// so two of them on top of each other are unreadable: at most one is on. Boundaries and masks are
// independent of it.

const isChoropleth = (layers, id) => layers.find((l) => l.id === id)?.kind === 'choropleth'

/** The set of active ids after switching `id` on or off; switching a choropleth on switches the others off. */
export function toggleLayer(active, id, on, layers) {
  const next = new Set(active)
  if (!on) {
    next.delete(id)
    return next
  }
  if (isChoropleth(layers, id)) {
    for (const other of [...next]) if (isChoropleth(layers, other)) next.delete(other)
  }
  next.add(id)
  return next
}

/** A list of ids (e.g. from an address) reduced to at most one choropleth, the first listed. */
export function oneChoropleth(ids, layers) {
  let seen = false
  return ids.filter((id) => {
    if (!isChoropleth(layers, id)) return true
    if (seen) return false
    seen = true
    return true
  })
}
