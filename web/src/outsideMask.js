// The "everything but the selected city" polygon that dims the map outside a functional area: the whole world with
// the outlines of the city's boundary features cut out. Built from the boundary GeoJSON that is already on the map,
// so it needs no extra data. Pure.

const LON = 180
const LAT = 85.0511
export const WORLD_RING = [[-LON, -LAT], [LON, -LAT], [LON, LAT], [-LON, LAT], [-LON, -LAT]]

/** The polygons (arrays of rings) of a Polygon or MultiPolygon geometry. */
const polygonsOf = (g) => (g?.type === 'Polygon' ? [g.coordinates] : g?.type === 'MultiPolygon' ? g.coordinates : [])

/**
 * A Feature (Polygon with holes, plus one polygon per island of the area) covering the world except the functional
 * area of agglomeration `id`; null when the features have none. Features with level "core" are the city inside the
 * area and are ignored: the area is the other features with that id.
 */
export function outsideMask(features, id) {
  const area = (features || []).filter((f) => f?.properties?.id === id && f.properties.level !== 'core')
  const polys = area.flatMap((f) => polygonsOf(f.geometry)).filter((p) => p.length && p[0].length >= 4)
  if (!id || !polys.length) return null
  // the world with every outer ring cut out; a ring inside an outer ring (a hole of the area) is outside again
  const holes = polys.map((p) => p[0])
  const islands = polys.flatMap((p) => p.slice(1)).map((ring) => [ring])
  const coordinates = [[WORLD_RING, ...holes], ...islands]
  return {
    type: 'Feature',
    properties: { id },
    geometry: islands.length ? { type: 'MultiPolygon', coordinates } : { type: 'Polygon', coordinates: coordinates[0] },
  }
}
