// Pieces the kit's DataTable is fed with: row actions and labels, city column heads, the value+rank columns of one city, and
// the reach blocks. The configurable table that uses them is in features/tables/.
import { DOMAIN_INFO } from './metricInfo'
import { SHORT_CITY } from './metricTable'

export const DASH = { content: '–', tone: 'dim', title: 'brak danych' }
export const NO_TIMETABLE = { content: '–', tone: 'dim', title: 'brak danych o rozkładach jazdy dla tej aglomeracji' }
export const GAP = { content: '', title: '' }

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
export function rowUnit(unit, moved, area) {
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

/** The column definitions of one city's table: the value in the chosen area and the rank among the cities that have the measure. */
export function valueColumns(area) {
  return [
    { key: 'v', head: DOMAIN_INFO[area]?.short || area, title: DOMAIN_INFO[area]?.title || area, align: 'right' },
    { key: 'pos', head: 'Poz.', title: 'Miejsce wśród aglomeracji, które mają tę miarę (tylko tam, gdzie „lepiej” coś znaczy)', narrow: true },
  ]
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
