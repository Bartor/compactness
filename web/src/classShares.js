// Residents and cells per colour class of the grid value layers (data/class_shares.json, written by
// pipeline.class_shares): {generated, layers: {layerId: {aggId | "all": {fua|core: {pop[], cells[], nodata_pop,
// nodata_cells}}}}}, classes in ramp order. Pure functions over that document; nothing here knows React.

/** The areas a share can refer to: the whole functional area or the core city. */
export const SHARE_AREAS = [
  { key: 'fua', label: 'cały obszar' },
  { key: 'core', label: 'miasto' },
]
export const DEFAULT_SHARE_AREA = 'fua'

/** The area the shares are given for when the page's area is `area`: the city for "Miasto", the whole area otherwise (the file has no more). */
export const shareAreaOf = (area) => (area === 'core' ? 'core' : 'fua')

/** Plain text saying that the shares are for the whole area although another one is chosen; '' when they match. */
export const shareAreaNote = (area) => (area === 'core' || area === 'fua' ? '' : 'Dla tego obszaru nie liczymy osobno, więc pokazujemy cały obszar.')

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const sum = (a) => a.reduce((x, y) => x + y, 0)

/**
 * The numbers of a layer for a scope: one agglomeration (`aggId`) or, with none, the whole coverage of the layer
 * ("all"); `area` is 'fua' or 'core'. Returns {agg, area, pop, cells, nodataPop, nodataCells, totalPop,
 * totalCells} or null when the file has nothing for it (no file, layer not covered, an empty area).
 * The totals include the no-data cells, so the shares of all classes and of no data add up to 1.
 */
export function scopeData(doc, layerId, aggId, area = DEFAULT_SHARE_AREA) {
  const key = aggId || 'all'
  const d = doc?.layers?.[layerId]?.[key]?.[area]
  if (!d || !Array.isArray(d.pop) || !Array.isArray(d.cells) || d.pop.length !== d.cells.length || !d.pop.length) return null
  const nodataPop = num(d.nodata_pop)
  const nodataCells = num(d.nodata_cells)
  const totalPop = sum(d.pop) + (nodataPop ?? 0)
  const totalCells = sum(d.cells) + (nodataCells ?? 0)
  if (!(totalCells > 0)) return null
  return { agg: key, area, pop: d.pop, cells: d.cells, nodataPop, nodataCells, totalPop, totalCells }
}

/**
 * Shares of residents and of cells per class: {pop: [fraction], cells: [fraction], nodataPop, nodataCells}, each of
 * the scope's total (no data included); a scope where nobody lives has all-zero resident shares.
 */
export function shareFractions(scope) {
  if (!scope) return null
  const f = (v, total) => (total > 0 ? v / total : 0)
  return {
    pop: scope.pop.map((v) => f(v, scope.totalPop)),
    cells: scope.cells.map((v) => f(v, scope.totalCells)),
    nodataPop: scope.nodataPop == null ? null : f(scope.nodataPop, scope.totalPop),
    nodataCells: scope.nodataCells == null ? null : f(scope.nodataCells, scope.totalCells),
  }
}

/** What the picked classes (indices in ramp order) add up to: {pop, cells, popShare, cellShare}; zeros when none. */
export function pickedSum(scope, picked) {
  const idx = [...new Set(picked)].filter((i) => Number.isInteger(i) && i >= 0 && i < (scope?.pop.length ?? 0))
  const pop = idx.reduce((a, i) => a + scope.pop[i], 0)
  const cells = idx.reduce((a, i) => a + scope.cells[i], 0)
  return {
    pop,
    cells,
    popShare: scope && scope.totalPop > 0 ? pop / scope.totalPop : 0,
    cellShare: scope && scope.totalCells > 0 ? cells / scope.totalCells : 0,
  }
}

/** The agglomerations a layer has numbers for, without "all". */
export const layerAggs = (doc, layerId) => Object.keys(doc?.layers?.[layerId] || {}).filter((k) => k !== 'all').sort()

/** "Wrocław, cały obszar" or "wszystkie miasta z tą warstwą, miasto": whose numbers a scope holds. */
export function scopeLabel(aggName, area = DEFAULT_SHARE_AREA) {
  const a = SHARE_AREAS.find((x) => x.key === area) || SHARE_AREAS[0]
  return `${aggName || 'wszystkie miasta z tą warstwą'}, ${a.label}`
}

/** "23 %" for class `i`, "<1 %" for a tiny share, '' when there is no number. `fractions` are of 1. */
export function shareText(fractions, i) {
  if (!Array.isArray(fractions)) return ''
  const v = fractions[i]
  if (typeof v !== 'number' || !Number.isFinite(v)) return ''
  const p = v * 100
  if (p > 0 && p < 1) return '<1 %'
  return `${Math.round(p)} %`
}
