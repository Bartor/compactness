// The line table of the speed view as pure data: parse results/web/speed/lines.json, filter it (city, mode, day
// type, band), sort values, and the two-way link keys between the table and the map. No React here.
import { BANDS, DEFAULT_BAND, MODE_GROUP, bandIndex, classOf } from './speedModel'

export const MODE_FILTERS = [
  { key: 'tram', label: 'tramwaje' },
  { key: 'bus', label: 'autobusy i trolejbusy' },
  { key: 'rail', label: 'metro i kolej' },
  { key: 'all', label: 'wszystkie' },
]
export const DAY_FILTERS = [{ key: 'weekday', label: 'środa' }, { key: 'saturday', label: 'sobota' }]
export const DEFAULT_FILTERS = Object.freeze({ city: null, mode: 'tram', day: 'weekday', band: DEFAULT_BAND })

/** lines.json (columnar) -> {bands, dates, rows: [{key, agg, mode, feed, line, term, official, v, n, hw, gap, sp, flags}]} */
export function parseLines(json) {
  if (!json || !Array.isArray(json.columns) || !Array.isArray(json.rows)) return { bands: BANDS, dates: null, rows: [] }
  const cols = json.columns
  const rows = json.rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])))
  return { bands: json.bands || BANDS, dates: json.timetable_dates || null, rows }
}

/** The bands of a day type, for the band chooser. */
export const bandsOfDay = (day) => BANDS.filter((b) => b.day === day)

/** A filter state that is consistent: the band belongs to the day type (else the day's first non-night band). */
export function normaliseFilters(f) {
  const day = f?.day === 'saturday' ? 'saturday' : 'weekday'
  const ok = bandsOfDay(day).some((b) => b.key === f?.band)
  const band = ok ? f.band : (day === 'weekday' ? DEFAULT_BAND : 's_d')
  const mode = MODE_FILTERS.some((m) => m.key === f?.mode) ? f.mode : DEFAULT_FILTERS.mode
  return { city: f?.city || null, mode, day, band }
}

/** Changes one filter; switching the day type moves the band to the same time of day where it can. */
export function setFilter(f, name, value) {
  const cur = normaliseFilters(f)
  if (name === 'day' && value !== cur.day) {
    const map = { w_n: 's_n', w_e: 's_mo', w_am: 's_mo', w_md: 's_d', w_pm: 's_d', w_ee: 's_ev', w_ev: 's_ev', w_all: 's_all',
      s_n: 'w_n', s_mo: 'w_am', s_d: 'w_md', s_ev: 'w_ev', s_all: 'w_all' }
    return normaliseFilters({ ...cur, day: value, band: map[cur.band] })
  }
  return normaliseFilters({ ...cur, [name]: value })
}

/** Rows of the table for the filters: only lines that run in the band (trips > 0). */
export function filterRows(rows, filters) {
  const f = normaliseFilters(filters)
  const i = bandIndex(f.band)
  return rows.filter((r) => (!f.city || r.agg === f.city)
    && (f.mode === 'all' || MODE_GROUP[r.mode] === f.mode)
    && Array.isArray(r.n) && (r.n[i] ?? 0) > 0)
}

const collator = new Intl.Collator('pl', { numeric: true, sensitivity: 'base' })
/** Natural order of line names: 2 < 10 < 10A < N1 < Z. */
export const compareLines = (a, b) => collator.compare(String(a), String(b))

/** Value of a row in a column, for display and sorting. */
export function cellValue(row, column, band) {
  const i = bandIndex(band)
  switch (column) {
    case 'v': return row.v?.[i] ?? null
    case 'cls': return classOf(row.v?.[i])
    case 'n': return row.n?.[i] ?? null
    case 'hw': return row.hw?.[i] ?? null
    case 'gap': return row.gap ?? null
    case 'sp': return row.sp ?? null
    default: return row[column] ?? null
  }
}

/** The rows in the default order: city, mode, line (natural). */
export function defaultOrder(rows) {
  const modeRank = { tram: 0, trolleybus: 1, bus: 2, metro: 3, rail: 4 }
  return [...rows].sort((a, b) => (a.agg < b.agg ? -1 : a.agg > b.agg ? 1 : 0)
    || (modeRank[a.mode] ?? 9) - (modeRank[b.mode] ?? 9) || compareLines(a.line, b.line) || (a.feed < b.feed ? -1 : a.feed > b.feed ? 1 : 0))
}

/** The map layer group ("tram" | "bus" | "rail") that draws a table row. */
export const groupOfRow = (row) => MODE_GROUP[row?.mode] || null

/** Row keys the table should light for a set of keys coming from the map (ignores keys not in the table). */
export function hotRowKeys(rows, keys) {
  if (!keys || !keys.length) return new Set()
  const want = new Set(keys)
  return new Set(rows.filter((r) => want.has(r.key)).map((r) => r.key))
}

/** Pins: toggles a key in a sorted list. */
export function togglePin(pinned, key) {
  const cur = pinned || []
  return cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key].sort()
}

/** Finds the row id of a DOM event target inside the table (the label carries data-row-id). */
export function rowIdFromTarget(target) {
  const tr = target && typeof target.closest === 'function' ? target.closest('tr') : null
  const tag = tr ? tr.querySelector('[data-row-id]') : null
  return tag ? tag.getAttribute('data-row-id') : null
}
