// Turns the metrics index into what the kit's DataTable draws: the comparison of cities in one area, and the table of
// one city across areas. Pure data in, plain objects (with JSX for the help) out.
import { METRIC_INFO, DOMAIN_INFO } from './metricInfo'
import { formatValue } from './metrics'
import MetricHelp from './MetricHelp'
import {
  AREAS, SHORT_CITY, areaRow, buildGroups, cityCell, markExtremes, metricName, metricUnit, plainText, standing, valueOf,
} from './metricTable'

const DASH = { content: '–', tone: 'dim', title: 'brak danych' }

/** The "na mapie" action of a metric, when its layer exists and is ready in the catalog. */
export function mapAction(info, id, layers, onShowLayer) {
  const layerId = info[id]?.layer
  if (!layerId || !layers.some((l) => l.id === layerId && l.status === 'ready')) return null
  return { label: 'na mapie', onClick: () => onShowLayer(layerId) }
}

/** Short column head of a city. */
export const cityHead = (id, names) => SHORT_CITY[id] || names[id] || id

/** Column definitions for cities: head, full name on hover, and a click that selects the city. */
export function cityColumns(cities, names, onPick) {
  return cities.map((c) => ({ key: c, head: cityHead(c, names), title: names[c] || c, onPick: onPick ? () => onPick(c) : undefined }))
}

/**
 * Groups of rows for the comparison: one column per city, all in `area`. Each row marks its best and weakest value
 * (METRIC_INFO's `better`), has the "?" with the explanation and, where a map layer shows the same thing, "na mapie".
 * A cell carries the number it sorts by apart from its text, and a row says which way is better, so that sorting the
 * row puts the best city first (a row without a direction goes from the highest).
 */
export function compareGroups({ index, cities, area, names, layers, onShowLayer, onlyGroups = null, info = METRIC_INFO }) {
  return buildGroups(index, { onlyGroups }).map((g) => ({
    id: g.id,
    title: g.title,
    rows: g.metrics.map((id) => {
      const rows = cities.map((c) => areaRow(index, id, c, area))
      const values = rows.map(valueOf)
      const marks = markExtremes(values, info[id]?.better)
      return {
        id,
        label: metricName(index, id, info),
        unit: metricUnit(index, id),
        better: info[id]?.better ?? null,
        help: <MetricHelp id={id} entries={cities.map((c, i) => ({ key: c, row: rows[i] }))} nameOf={(c) => names[c] || c} info={info} />,
        action: mapAction(info, id, layers, onShowLayer),
        cells: values.map((v, i) => (v == null
          ? DASH
          : { content: plainText(rows[i]), value: v, title: formatValue(rows[i]).text, tone: marks.best.has(i) ? 'best' : marks.worst.has(i) ? 'weak' : undefined })),
      }
    }),
  }))
}

/** Column definitions of the areas of one city's table, with a narrow rank column last. */
export function areaColumns() {
  return [
    ...AREAS.map((a) => ({
      key: a, head: DOMAIN_INFO[a].short, title: DOMAIN_INFO[a].title,
      help: <p>{DOMAIN_INFO[a].read}</p>,
    })),
    { key: 'pos', head: 'Poz.', title: 'Miejsce wśród miast z danymi o transporcie, w obszarze „Miasto”', narrow: true },
  ]
}

/**
 * Groups of rows for one city: a column per area and the city's rank among `cities` (n/7, in the core area, or the
 * first area that has the metric). Metrics the city has no row for are left out.
 */
export function cityGroups({ index, cities, agg, layers, onShowLayer, info = METRIC_INFO }) {
  const areaName = (a) => DOMAIN_INFO[a]?.short || a
  return buildGroups(index).map((g) => ({
    id: g.id,
    title: g.title,
    rows: g.metrics.filter((id) => AREAS.some((a) => cityCell(index, id, agg, a))).map((id) => {
      const rows = AREAS.map((a) => cityCell(index, id, agg, a))
      const better = info[id]?.better
      const st = standing(index, id, cities, agg, better)
      const pos = !st
        ? DASH
        : {
          content: `${st.rank}/${st.n}`,
          tone: better == null ? 'dim' : st.rank === 1 ? 'best' : undefined,
          title: `Miejsce wśród ${st.n} miast, w obszarze „${areaName(st.area)}”${better == null ? ' (miara bez kierunku „lepiej”)' : ''}`,
        }
      return {
        id,
        label: metricName(index, id, info),
        unit: metricUnit(index, id),
        help: <MetricHelp id={id} entries={AREAS.map((a, i) => ({ key: a, row: rows[i] }))} nameOf={areaName} info={info} />,
        action: mapAction(info, id, layers, onShowLayer),
        cells: [
          ...rows.map((r) => (valueOf(r) == null ? DASH : { content: plainText(r), title: formatValue(r).text })),
          pos,
        ],
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
