// The data of each chart as a flat table {head, rows}: exactly what is drawn, one row per drawn value, with city ids
// beside names. No app imports; the app wraps these with the provenance of the project (export/shape.js chartTable).
// Missing values are null (an empty cell in the CSV), never 0.

const n = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/** At-least curves: one row per series and x. `xName` names the x column. */
export function atLeastTable(series, { xName = 'x', unit = '%' } = {}) {
  const rows = []
  for (const s of series) {
    const xs = s.xs || []
    xs.forEach((x, i) => rows.push([s.key, s.label, n(x), n(s.ys?.[i])]))
  }
  return { head: ['miasto_id', 'miasto', xName, `odsetek mieszkańców, ${unit === 'min' ? '%' : unit}`], rows }
}

/** Reach curves with their quartile band. */
export function reachTable(series) {
  const rows = []
  for (const s of series) {
    (s.xs || []).forEach((x, i) => rows.push([
      s.key, s.label, n(x), n(s.rom?.[i]), n(s.mor?.[i]), n(s.p25?.[i]), n(s.p50?.[i]), n(s.p75?.[i]),
    ]))
  }
  return {
    head: ['miasto_id', 'miasto', 'czas podróży, min', 'zasięg (stosunek średnich), %', 'zasięg (średnia stosunków), %',
      'percentyl 25, %', 'mediana, %', 'percentyl 75, %'],
    rows,
  }
}

/** One value per city, in the order drawn, and the median. */
export function valuesTable(rows, { label = 'wartość', unit = '', median = null, medianLabel = 'mediana' } = {}) {
  const out = rows.map((r) => [r.key, r.label, n(r.value), unit])
  if (median != null) out.push(['mediana', medianLabel, n(median), unit])
  return { head: ['miasto_id', 'miasto', label, 'jednostka'], rows: out }
}

/** Two values per city and their difference. */
export function pairTable(rows, { aLabel = 'a', bLabel = 'b', unit = '' } = {}) {
  return {
    head: ['miasto_id', 'miasto', aLabel, bLabel, `różnica (${bLabel} − ${aLabel})`, 'jednostka'],
    rows: rows.map((r) => [r.key, r.label, n(r.a), n(r.b), n(r.a) != null && n(r.b) != null ? r.b - r.a : null, unit]),
  }
}

/** Time of day: the 30 and 45 minute values per window, and the comparison rows when given. */
export function timeTable(rows, compare = null, { unit = '%', compareLabel = 'mediana siedmiu miast' } = {}) {
  const out = rows.map((r) => ['miasto', r.key, r.label, n(r.v30), n(r.v45), unit])
  for (const r of compare || []) out.push([compareLabel, r.key, r.label, n(r.v30), n(r.v45), unit])
  return { head: ['seria', 'pora_id', 'pora', '30 min', '45 min', 'jednostka'], rows: out }
}
