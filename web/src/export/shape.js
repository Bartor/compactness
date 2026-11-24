// What each view exports, as rows of cells (header first): tables from the metrics index, in the order the table is
// shown. One row per value, with stable ids beside the Polish labels, the unit, the direction of "better", and at the
// end the provenance that every number of the project carries: source, population grid, dates, remarks. Pure.
import { METRIC_INFO, DOMAIN_INFO } from '../metricInfo'
import { POPULATION_GRIDS } from '../metrics'
import { AREAS, TRAM_DOMAIN, areaRow, buildGroups, cityCell, metricName, valueOf } from '../metricTable'

export const PROVENANCE_HEAD = ['źródło', 'siatka ludności', 'data ludności', 'data rozkładów', 'uwagi']
const DIRECTION = { higher: 'wyżej = lepiej', lower: 'niżej = lepiej' }

/** The provenance cells of a metrics row (empty strings when the row carries nothing). */
export function provenanceCells(row) {
  if (!row) return ['', '', '', '', '']
  const grid = row.population_grid ? POPULATION_GRIDS[row.population_grid] || row.population_grid : row.grid
  return [row.source ?? '', grid ?? '', row.population_date ?? '', row.timetable_date ?? '', row.flag ?? '']
}

/** What a chart file has no row for: the project's usual provenance, taken from the metrics rows (the first that has each). */
export function metaFromRows(rows) {
  const first = (get) => rows.map(get).find((v) => v != null && v !== '')
  const grid = first((r) => (r.population_grid ? POPULATION_GRIDS[r.population_grid] || r.population_grid : null))
  return {
    source: 'wydawcy GTFS, OpenStreetMap, GUS (NSP 2021), JRC GHSL',
    populationGrid: grid || '',
    populationDate: first((r) => r.population_date) || '',
    timetableDate: first((r) => r.timetable_date) || '',
  }
}

/** The provenance cells of a chart from `metaFromRows`. */
export const metaCells = (meta) => [meta?.source ?? '', meta?.populationGrid ?? '', meta?.populationDate ?? '', meta?.timetableDate ?? '', '']

export const areaLabel = (a) => DOMAIN_INFO[a]?.short || a

/** The cities in the order a comparison table shows them: sorted by the row of `sort.key` (missing last), else as given. */
export function orderCities(cities, index, area, sort) {
  if (!sort?.key) return [...cities]
  const sgn = sort.dir === 'asc' ? 1 : -1
  const val = (c) => valueOf(areaRow(index, sort.key, c, area))
  return cities.map((c, i) => [c, i, val(c)]).sort((a, b) => {
    if (a[2] == null || b[2] == null) return (a[2] == null) - (b[2] == null) || a[1] - b[1]
    return sgn * (a[2] - b[2]) || a[1] - b[1]
  }).map((x) => x[0])
}

const HEAD_ROWS = [
  'miara_id', 'miara', 'grupa', 'miasto_id', 'miasto', 'obszar_id', 'obszar', 'wartość', 'jednostka', 'lepiej',
  'miejsce w tabeli',
]

/**
 * The comparison of cities in one area: a row per measure and city, measures in the table's order, cities in the
 * order shown (a sorted table exports sorted). `groups` is buildGroups' output as the table used it.
 */
export function comparisonTable({ index, cities, area, names, groups, sort, info = METRIC_INFO }) {
  const shown = orderCities(cities, index, area, sort)
  const rows = [[...HEAD_ROWS, ...PROVENANCE_HEAD]]
  for (const g of groups) {
    for (const id of g.metrics) {
      shown.forEach((c, i) => {
        const r = areaRow(index, id, c, area)
        rows.push([
          id, metricName(index, id, info), g.title, c, names[c] || c, r?.domain ?? area, areaLabel(r?.domain ?? area),
          valueOf(r), r?.unit ?? '', DIRECTION[info[id]?.better] ?? '', i + 1, ...provenanceCells(r),
        ])
      })
    }
  }
  return rows
}

/** One city: a row per measure and area. */
export function cityTable({ index, agg, name, groups, info = METRIC_INFO }) {
  const rows = [['miara_id', 'miara', 'grupa', 'miasto_id', 'miasto', 'obszar_id', 'obszar', 'wartość', 'jednostka', 'lepiej', ...PROVENANCE_HEAD]]
  for (const g of groups) {
    for (const id of g.metrics) {
      for (const a of AREAS) {
        const r = cityCell(index, id, agg, a)
        if (!r) continue
        rows.push([
          id, metricName(index, id, info), g.title, agg, name, r.domain, areaLabel(r.domain), valueOf(r), r.unit ?? '',
          DIRECTION[info[id]?.better] ?? '', ...provenanceCells(r),
        ])
      }
    }
  }
  return rows
}

/** The groups of the main table (what buildGroups gives for the index), for callers that have only the index. */
export const tableGroups = (index, opts) => buildGroups(index, opts)

/** One metric on its page: a row per city and area, with the rank in the area shown (1 = best; ties share it). */
export function metricTable({ index, id, cityIds, names, areas, area, info = METRIC_INFO }) {
  const better = info[id]?.better
  const inArea = cityIds.map((c) => ({ c, v: valueOf(index[id]?.[c]?.[area]) })).filter((x) => x.v != null)
  const rank = (c) => {
    const mine = inArea.find((x) => x.c === c)
    return mine ? 1 + inArea.filter((o) => (better === 'lower' ? o.v < mine.v : o.v > mine.v)).length : ''
  }
  const rows = [[
    'miara_id', 'miara', 'miasto_id', 'miasto', 'obszar_id', 'obszar', 'wartość', 'jednostka', 'lepiej',
    `miejsce w obszarze ${areaLabel(area)}`, ...PROVENANCE_HEAD,
  ]]
  for (const c of cityIds) {
    for (const a of areas) {
      const r = index[id]?.[c]?.[a] ?? null
      rows.push([
        id, metricName(index, id, info), c, names[c] || c, a, areaLabel(a), valueOf(r), r?.unit ?? '',
        DIRECTION[info[id]?.better] ?? '', a === area ? rank(c) : '', ...provenanceCells(r),
      ])
    }
  }
  return rows
}

export { TRAM_DOMAIN }

/**
 * A chart's data as a CSV table: `data` is {head, rows} (what the chart draws, one row per drawn value), prefixed with
 * the chart's title and area and followed by the provenance of the project (`meta` from metaFromRows).
 */
export function chartTable({ title, area = { id: 'core', label: 'Miasto' } }, data, meta) {
  return [
    ['wykres', 'obszar_id', 'obszar', ...data.head, ...PROVENANCE_HEAD],
    ...data.rows.map((r) => [title, area.id, area.label, ...r, ...metaCells(meta)]),
  ]
}

/** The classes of a value layer for one scope: residents and cells per class (and no data), as the chart's table shows them. */
export function classTable({ layerTitle, labels, scope, aggId, aggName, nodataLabel }, meta) {
  const pct = (v, total) => (total > 0 ? (100 * v) / total : null)
  const rows = labels.map((l, i) => [i + 1, l, scope.pop[i], pct(scope.pop[i], scope.totalPop), scope.cells[i], pct(scope.cells[i], scope.totalCells)])
  if (scope.nodataPop != null) {
    rows.push(['', nodataLabel, scope.nodataPop, pct(scope.nodataPop, scope.totalPop), scope.nodataCells, pct(scope.nodataCells, scope.totalCells)])
  }
  const head = ['klasa_nr', 'klasa', 'mieszkańcy', '% mieszkańców', 'komórki 250 m', '% komórek']
  const data = { head: ['warstwa', 'miasto_id', 'miasto', ...head], rows: rows.map((r) => [layerTitle, aggId || 'all', aggName || 'wszystkie miasta z tą warstwą', ...r]) }
  const area = { id: scope.area, label: scope.area === 'core' ? 'miasto' : 'cały obszar' }
  return chartTable({ title: `Mieszkańcy według klas: ${layerTitle}`, area }, data, meta)
}

/** The same for many cities: a row per city and class. `perCity` is [{id, name, scope}]. */
export function classCitiesTable({ layerTitle, labels, perCity, area, nodataLabel }, meta) {
  const rows = []
  for (const { id, name, scope } of perCity) {
    const share = (v) => (scope.totalPop > 0 ? (100 * v) / scope.totalPop : null)
    labels.forEach((l, i) => rows.push([id, name, i + 1, l, scope.pop[i], share(scope.pop[i])]))
    if (scope.nodataPop != null) rows.push([id, name, '', nodataLabel, scope.nodataPop, share(scope.nodataPop)])
  }
  const data = { head: ['miasto_id', 'miasto', 'klasa_nr', 'klasa', 'mieszkańcy', '% mieszkańców miasta'], rows }
  return chartTable({ title: `Mieszkańcy według klas: ${layerTitle}`, area: { id: area, label: area === 'core' ? 'miasto' : 'cały obszar' } }, data, meta)
}
