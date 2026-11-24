// Small geometry helpers for the map page: which agglomeration a point is in, from the boundary features that are already loaded.

/** True when [x, y] is inside the ring (even-odd rule). */
function inRing(x, y, ring) {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

const inPolygon = (x, y, rings) => rings.length > 0 && inRing(x, y, rings[0]) && !rings.slice(1).some((r) => inRing(x, y, r))

/** The id of the agglomeration whose functional area (features not at level "core") holds the point, or null. */
export function cityAtPoint(features, lng, lat) {
  for (const f of features || []) {
    const g = f.geometry
    if (!g || f.properties?.level === 'core' || !f.properties?.id) continue
    const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : []
    if (polys.some((p) => inPolygon(lng, lat, p))) return f.properties.id
  }
  return null
}
