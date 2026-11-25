// The rows and columns of the configurable table, in the shape the kit's DataTable takes. Pure data in; plain objects
// (with a little JSX for labels and the help) out. Which shape: spec.js shapeOf.
//   cities   rows are measures, columns are cities, read in one area (a measure that has no values there is read in the
//            nearest area that has, and says so in its small print)
//   areas    one city, columns are the areas
//   subarea  several cities and areas: columns are cities, a measure has a sub-row per area
//   subcity  the same exchanged: columns are areas, a measure has a sub-row per city
//   value    one city in one area: the value and its rank among the agglomerations
import { METRIC_INFO, DOMAIN_INFO } from '../../metricInfo'
import { formatValue } from '../../metrics'
import { ShortHelp } from '../../MetricHelp'
import {
  TRAM_DOMAIN, areaRow, markExtremes, metricName, metricUnit, plainText, rankAmong, resolveRowArea, valueOf,
} from '../../metricTable'
import { DASH, GAP, NO_TIMETABLE, cityColumns, rowActions, rowLabel, rowUnit, valueColumns } from '../../tableModel'
import { needsTimetable, subKey } from './spec'

/** A shown cell with no figure but a reason: the tram network is one number for the whole city. */
const NETWORK = { content: '', tone: 'dim', title: 'sieć tramwajowa: jedna liczba dla całego miasta (w pierwszej kolumnie)' }

const areaShort = (a) => DOMAIN_INFO[a]?.short || a
const isEmpty = (c) => c === DASH || c === NO_TIMETABLE || c === GAP || c === NETWORK || c.content === '' || c.content == null

/** True when the measure is only a tram-network figure for every city that has it (it belongs to no area). */
export function tramOnly(index, id, cities) {
  const have = cities.map((c) => index[id]?.[c]).filter(Boolean)
  return have.length > 0 && have.every((m) => Object.keys(m).every((k) => k === TRAM_DOMAIN))
}

const strict = (index, id, c, a) => index[id]?.[c]?.[a] ?? null

/** The cell of a figure; `tone` marks the best and the weakest. */
function figure(row, tone) {
  const v = valueOf(row)
  if (v == null) return DASH
  return { content: plainText(row), value: v, title: formatValue(row).text, tone }
}

/**
 * The model of the table: {columns, groups, flat, rowCount, hidden, moved, lackTimetable, records}.
 * `groups` is [{id, title, rows}] (the rows of the kit); `flat` says to show the rows without headings. `hidden` counts the
 * measures that have no figure anywhere in the table (left out), `moved` is true when a row is read in another area than
 * the asked one, `lackTimetable` lists the chosen cities without timetables when the selection has measures that need them.
 * `records` is what the CSV needs: one per shown cell, {rowKey, id, group, col, city, area, row}.
 * `grouped`: put the thin divider between the cities with and without timetables (columns are cities, no sort).
 */
export function buildTable({
  index, selection, cities, areas, shape, names, layers, onShowLayer, onOpenMetric, onPickCity, transport, everyCity,
  grouped = false, info = METRIC_INFO,
}) {
  const withTt = cities.filter((c) => transport.includes(c))
  const without = cities.filter((c) => !transport.includes(c))
  const ordered = shape.cols === 'cities' ? [...withTt, ...without] : cities
  const none = new Set(everyCity.filter((c) => !transport.includes(c)))
  const gapped = grouped && shape.cols === 'cities' && withTt.length > 0 && without.length > 0
  const gapAfter = gapped ? without[0] : null
  const cityName = (c) => names[c] || c

  let columns
  if (shape.cols === 'cities') columns = cityColumns(ordered, names, onPickCity, gapped ? { transport: withTt, rest: without } : null)
  else if (shape.cols === 'areas') columns = areas.map((a) => ({ key: a, head: areaShort(a), title: DOMAIN_INFO[a]?.title || a, name: areaShort(a) }))
  else columns = valueColumns(areas[0])

  const sortable = shape.cols === 'cities'
  const records = []
  let moved = false
  let hidden = 0
  const unitOf = (id) => metricUnit(index, id)

  /** The cell of a city that has no figure: a missing timetable is said in the cell's tooltip. */
  const gone = (id, c) => (none.has(c) && needsTimetable(index, id, [...none]) ? NO_TIMETABLE : DASH)

  const meta = (id) => ({
    help: <ShortHelp id={id} info={info} onOpen={onOpenMetric && (() => onOpenMetric(id))} />,
    ...rowActions(info, id, layers, onShowLayer, onOpenMetric),
  })

  /** Cells of a row whose columns are cities, from the row of each city. Marks the best and weakest. */
  const cityCells = (id, rows) => {
    const values = rows.map(valueOf)
    const marks = markExtremes(values, info[id]?.better)
    const cells = []
    ordered.forEach((c, i) => {
      if (gapAfter && c === gapAfter) cells.push(GAP)
      cells.push(values[i] == null ? gone(id, c) : figure(rows[i], marks.best.has(i) ? 'best' : marks.worst.has(i) ? 'weak' : undefined))
    })
    return cells
  }

  /** The cell of a city in an area for a table whose columns are areas; the tram network stands in the first column only. */
  const areaCell = (id, c, a, first) => {
    const m = index[id]?.[c]
    const row = m?.[a] ?? (first ? m?.[TRAM_DOMAIN] ?? null : null)
    if (row) return { cell: figure(row), row }
    return { cell: !first && m?.[TRAM_DOMAIN] ? NETWORK : DASH, row: null }
  }

  const baseRow = (id, over) => ({
    id, better: info[id]?.better ?? null, sortable, ...over,
  })

  const out = []
  const rowsOf = (id, group) => {
    const name = metricName(index, id, info)
    const unit = unitOf(id)
    // a row that cannot sort has a name that opens the metric's page; a sortable one is the kit's sort button
    const plain = sortable ? name : rowLabel(name, id, onOpenMetric)
    const found = []
    const add = (row, recs) => { found.push({ row, recs }) }

    if (shape.key === 'cities' || (shape.key === 'subarea' && tramOnly(index, id, ordered))) {
      const at = resolveRowArea(index, id, ordered, areas[0])
      const rows = ordered.map((c) => areaRow(index, id, c, at.area))
      add(baseRow(id, {
        label: plain, name, unit: rowUnit(unit, at.moved, at.area), ...meta(id), cells: cityCells(id, rows), movedTo: at.moved ? at.area : null,
      }), ordered.map((c, i) => ({ rowKey: id, id, group, col: c, city: c, area: rows[i]?.domain ?? at.area, row: rows[i] })))
    } else if (shape.key === 'subarea') {
      let first = true
      for (const a of areas) {
        const rows = ordered.map((c) => strict(index, id, c, a))
        if (rows.every((r) => valueOf(r) == null)) continue
        const key = subKey(id, a)
        add(baseRow(key, first
          ? { label: <><span>{name}</span><span className="tb-sub"> · {areaShort(a)}</span></>, name: `${name}, ${areaShort(a)}`, unit, ...meta(id), cells: cityCells(id, rows) }
          : { label: <span className="tb-sub tb-indent">{areaShort(a)}</span>, name: `${name}, ${areaShort(a)}`, cells: cityCells(id, rows) }),
        ordered.map((c, i) => ({ rowKey: key, id, group, col: c, city: c, area: a, row: rows[i] })))
        first = false
      }
    } else if (shape.key === 'areas') {
      const c = cities[0]
      const got = areas.map((a, i) => areaCell(id, c, a, i === 0))
      add(baseRow(id, { label: plain, name, unit, ...meta(id), cells: got.map((g) => g.cell) }),
        areas.map((a, i) => ({ rowKey: id, id, group, col: a, city: c, area: got[i].row?.domain ?? a, row: got[i].row })))
    } else if (shape.key === 'subcity') {
      let first = true
      for (const c of cities) {
        const got = areas.map((a, i) => areaCell(id, c, a, i === 0))
        if (got.every((g) => g.row == null)) continue
        const key = subKey(id, c)
        add(baseRow(key, first
          ? { label: <><span>{name}</span><span className="tb-sub"> · {cityName(c)}</span></>, name: `${name}, ${cityName(c)}`, unit, ...meta(id), cells: got.map((g) => g.cell) }
          : { label: <span className="tb-sub tb-indent">{cityName(c)}</span>, name: `${name}, ${cityName(c)}`, cells: got.map((g) => g.cell) }),
        areas.map((a, i) => ({ rowKey: key, id, group, col: a, city: c, area: got[i].row?.domain ?? a, row: got[i].row })))
        first = false
      }
    } else {
      const agg = cities[0]
      if (!index[id]?.[agg]) return []
      const area = areas[0]
      const at = resolveRowArea(index, id, [agg], area)
      const row = areaRow(index, id, agg, at.area)
      const st = rankAmong(index, id, everyCity, agg, area, info[id]?.better)
      const pos = !info[id]?.better || !st
        ? { content: '', tone: 'dim', title: info[id]?.better ? 'brak miejsca: za mało miast z tą miarą' : 'miara bez kierunku „lepiej”: nie układamy miejsc' }
        : { content: `${st.rank}/${st.n}`, tone: st.rank === 1 ? 'best' : undefined, title: `Miejsce ${st.rank} z ${st.n} aglomeracji, które mają tę miarę` }
      add(baseRow(id, { label: plain, name, unit: rowUnit(unit, at.moved, at.area), ...meta(id), cells: [figure(row), pos], movedTo: at.moved ? at.area : null }),
        [{ rowKey: id, id, group, col: 'v', city: agg, area: row?.domain ?? at.area, row }])
    }
    return found
  }

  for (const g of selection.groups) {
    const rows = []
    for (const id of g.metrics) {
      const found = rowsOf(id, g.title).filter((f) => !f.row.cells.every(isEmpty))
      if (!found.length) { hidden += 1; continue }
      for (const f of found) {
        rows.push(f.row)
        records.push(...f.recs)
        if (f.row.movedTo) moved = true
      }
    }
    if (rows.length) out.push({ id: g.id, title: g.title, rows })
  }

  const lackTimetable = without.length && selection.ids.some((id) => needsTimetable(index, id, [...none])) ? without : []
  return {
    columns, groups: out, flat: selection.flat, rowCount: out.reduce((n, g) => n + g.rows.length, 0), hidden, moved, lackTimetable,
    records, shape: shape.key, gapped,
  }
}

/**
 * The records of a built table in the order it is shown: the columns follow the sorted row when there is a sort (missing
 * figures last), the rows follow the table. Adds `place` (the position of the column) for tables whose columns are cities.
 */
export function orderedRecords(model, sort) {
  const sorted = sort?.key ? model.records.filter((r) => r.rowKey === sort.key) : []
  let order = null
  if (sorted.length) {
    const sgn = sort.dir === 'asc' ? 1 : -1
    order = sorted.map((r, i) => [r.col, i, valueOf(r.row)]).sort((a, b) => {
      if (a[2] == null || b[2] == null) return (a[2] == null) - (b[2] == null) || a[1] - b[1]
      return sgn * (a[2] - b[2]) || a[1] - b[1]
    }).map((x) => x[0])
  }
  const rank = (col, i) => (order ? order.indexOf(col) : i)
  const out = []
  let at = 0
  while (at < model.records.length) {
    const key = model.records[at].rowKey
    let end = at
    while (end < model.records.length && model.records[end].rowKey === key) end += 1
    const part = model.records.slice(at, end).map((r, i) => ({ ...r, i }))
    part.sort((a, b) => rank(a.col, a.i) - rank(b.col, b.i))
    part.forEach((r, i) => out.push({ ...r, place: model.shape === 'cities' || model.shape === 'subarea' ? i + 1 : '' }))
    at = end
  }
  return out
}
