// Turns the metrics index into what the kit's DataTable draws: the one table of all agglomerations in the chosen area, and
// the table of one city. Pure data in, plain objects (with JSX for the help) out.
import { METRIC_INFO, DOMAIN_INFO } from './metricInfo'
import { formatValue } from './metrics'
import { ShortHelp } from './MetricHelp'
import {
  SHORT_CITY, areaRow, buildGroups, markExtremes, metricName, metricUnit, plainText, rankAmong, resolveRowArea, valueOf,
} from './metricTable'

const DASH = { content: '–', tone: 'dim', title: 'brak danych' }
const NO_TIMETABLE = { content: '–', tone: 'dim', title: 'brak danych o rozkładach jazdy dla tej aglomeracji' }
const GAP = { content: '', title: '' }

/** The "na mapie" action of a metric (it shows the layer; the chosen layer card flashes), when its layer exists and is ready in the catalog. */
export function mapAction(info, id, layers, onShowLayer) {
  const layerId = info[id]?.layer
  if (!layerId || !layers.some((l) => l.id === layerId && l.status === 'ready')) return null
  return { label: 'na mapie', title: 'Pokaż tę miarę na mapie', onClick: () => onShowLayer(layerId) }
}

/** The "więcej" action: opens the page of one metric. */
export const pageAction = (id, onOpenMetric) => (onOpenMetric
  ? { label: 'więcej', title: 'Otwórz stronę miary: wszystkie miasta, opis i źródła', onClick: () => onOpenMetric(id) }
  : null)

/** The actions of a row of a table: "na mapie" (when the metric has a layer) and "więcej" (the metric's page). Rows carry `actions` only. */
export function rowActions(info, id, layers, onShowLayer, onOpenMetric) {
  const actions = [mapAction(info, id, layers, onShowLayer), pageAction(id, onOpenMetric)].filter(Boolean)
  return { actions: actions.length ? actions : undefined }
}

/** The label of a row: the metric's name as a link-like button that opens its page (a plain name without a page to open). */
export function rowLabel(name, id, onOpenMetric) {
  return onOpenMetric
    ? <button type="button" className="metric-link" title="Otwórz stronę miary" onClick={() => onOpenMetric(id)}>{name}</button>
    : name
}

/** The column head of a city: its name when that is short, else the short form (the full name is in the tooltip). */
export function cityHead(id, names) {
  const full = names[id]
  return full && full.length <= 10 ? full : SHORT_CITY[id] || full || id
}

/** The small print after a row's name: the unit, and where the row is read in another area than the one asked for. */
function rowUnit(unit, moved, area) {
  if (!moved) return unit
  return `${unit ? `${unit} · ` : ''}obszar: ${DOMAIN_INFO[area]?.short || area}`
}

/**
 * Column definitions for the cities of the comparison: head, full name on hover, a click that opens the city. With
 * `groups` ({transport: [ids], rest: [ids]}) the first column of each group carries a small caption and a thin empty column
 * separates the two groups; without it (a sorted table mixes the cities) the columns are plain.
 */
export function cityColumns(cities, names, onPick, groups = null) {
  const cols = []
  cities.forEach((c) => {
    const first = groups && (c === groups.transport[0] || c === groups.rest[0])
    if (groups && c === groups.rest[0] && groups.transport.length) cols.push({ key: '__gap', head: '', narrow: true, name: 'przerwa', sortable: false })
    const cap = c === groups?.transport[0] ? 'z danymi o transporcie' : c === groups?.rest[0] ? 'tylko gęstość i forma' : null
    cols.push({
      key: c,
      head: first ? <span className="col-group">{cap && <small className="col-cap">{cap}</small>}{cityHead(c, names)}</span> : cityHead(c, names),
      title: names[c] || c, name: names[c] || c, onPick: onPick ? () => onPick(c) : undefined,
    })
  })
  return cols
}

/** Groups whose measures exist for a single area (the whole functional area). */
const ONE_AREA_GROUPS = new Set(['poly'])

/**
 * Groups of rows for the comparison: one column per city (all agglomerations; the cities without timetables get a dash on
 * transport measures), read in `area`, or for a measure that has no values there in the nearest area that has (said in the
 * row's small print). Each row marks its best and weakest value, has the short "?" and its actions. A cell carries the
 * number it sorts by apart from its text, and a row says which way is better.
 * `columnsOf` is the order of the columns, as cityColumns got them (cities, and the gap column when there is one).
 */
export function compareGroups({
  index, cities, area, names, layers, onShowLayer, onOpenMetric, onlyGroups = null, info = METRIC_INFO, gapAfter = null, noTimetable = [],
}) {
  const none = new Set(noTimetable)
  return buildGroups(index, { onlyGroups }).map((g) => ({
    id: g.id,
    title: g.title,
    rows: g.metrics.map((id) => {
      const at = resolveRowArea(index, id, cities, area)
      const rows = cities.map((c) => areaRow(index, id, c, at.area))
      const values = rows.map(valueOf)
      const marks = markExtremes(values, info[id]?.better)
      const cells = []
      values.forEach((v, i) => {
        if (gapAfter && cities[i] === gapAfter) cells.push(GAP)
        cells.push(v == null
          ? (none.has(cities[i]) && !metricHasOnlyDensity(id) ? NO_TIMETABLE : DASH)
          : { content: plainText(rows[i]), value: v, title: formatValue(rows[i]).text, tone: marks.best.has(i) ? 'best' : marks.worst.has(i) ? 'weak' : undefined })
      })
      return {
        id,
        // the label is the kit's sort control in this table (sorting the cities by the row), so it stays plain text: the page
        // opens from "strona miary" and from the "?"
        label: metricName(index, id, info),
        name: metricName(index, id, info),
        unit: rowUnit(metricUnit(index, id), at.moved, at.area),
        better: info[id]?.better ?? null,
        help: <ShortHelp id={id} info={info} onOpen={onOpenMetric && (() => onOpenMetric(id))} />,
        ...rowActions(info, id, layers, onShowLayer, onOpenMetric),
        cells,
        movedTo: at.moved ? at.area : null,
      }
    }),
    // groups computed for one area only are left out elsewhere instead of being shown as rows of dashes
  })).filter((g) => !ONE_AREA_GROUPS.has(g.id) || g.rows.some((r) => r.cells.some((c) => c !== DASH && c !== NO_TIMETABLE && c !== GAP)))
}

// density and form measures exist for every agglomeration; a dash there would not be a missing timetable
const DENSITY_ONLY = new Set(['area', 'population_census', 'density_gross', 'pwdens_census_1km', 'rho_t20', 'rho_nearest_t20',
  'profile_r50_km', 'share_residents_ge5000', 'median_resident_density_250m', 'degurba2021_share_urban_centre'])
const metricHasOnlyDensity = (id) => DENSITY_ONLY.has(id)

/** The column definitions of one city's table: the value in the chosen area and the rank among the cities that have the measure. */
export function valueColumns(area) {
  return [
    { key: 'v', head: DOMAIN_INFO[area]?.short || area, title: DOMAIN_INFO[area]?.title || area, align: 'right' },
    { key: 'pos', head: 'Poz.', title: 'Miejsce wśród aglomeracji, które mają tę miarę (tylko tam, gdzie „lepiej” coś znaczy)', narrow: true },
  ]
}

/**
 * Groups of rows for one city in `area`: the value, and the rank among `pool` (all agglomerations) as n/N, blank for a
 * measure without a direction. Metrics the city has no row for are left out. A row read in another area (the chosen one
 * has no numbers for it) says so in its small print.
 */
export function cityGroups({ index, pool, agg, area, layers, onShowLayer, onOpenMetric, info = METRIC_INFO }) {
  return buildGroups(index).map((g) => ({
    id: g.id,
    title: g.title,
    rows: g.metrics.filter((id) => index[id]?.[agg]).map((id) => {
      const at = resolveRowArea(index, id, [agg], area)
      const row = areaRow(index, id, agg, at.area)
      const better = info[id]?.better
      const st = rankAmong(index, id, pool, agg, area, better)
      const pos = !better || !st
        ? { content: '', tone: 'dim', title: better ? 'brak miejsca: za mało miast z tą miarą' : 'miara bez kierunku „lepiej”: nie układamy miejsc' }
        : {
          content: `${st.rank}/${st.n}`,
          tone: st.rank === 1 ? 'best' : undefined,
          title: `Miejsce ${st.rank} z ${st.n} aglomeracji, które mają tę miarę`,
        }
      return {
        id,
        label: rowLabel(metricName(index, id, info), id, onOpenMetric),
        name: metricName(index, id, info),
        unit: rowUnit(metricUnit(index, id), at.moved, at.area),
        help: <ShortHelp id={id} info={info} onOpen={onOpenMetric && (() => onOpenMetric(id))} />,
        ...rowActions(info, id, layers, onShowLayer, onOpenMetric),
        cells: [valueOf(row) == null ? DASH : { content: plainText(row), title: formatValue(row).text, value: valueOf(row) }, pos],
      }
    }),
  })).filter((g) => g.rows.length > 0)
}

/** A one-group table of (30 min, 45 min) figures: "Pora dnia" and "Z centrów". `rows` is [{key, label, v30, v45, unit}]. */
export function reachGroups(rows, title) {
  const fmt = (v, unit) => (v == null ? DASH : { content: new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v), title: unit ? `${v} ${unit}` : undefined })
  return [{
    id: 'reach',
    title,
    rows: rows.map((r) => ({ id: r.key || r.domain, label: r.label, cells: [fmt(r.v30, r.unit), fmt(r.v45, r.unit)] })),
  }]
}
