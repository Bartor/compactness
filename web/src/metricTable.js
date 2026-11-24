// Pure logic of the metric tables: the index of the metrics file, which cities and metrics a table has, ranking
// with the direction of "better", best and weakest marks, the "co wyróżnia" statements, the time-of-day and
// centre blocks, the busiest stop areas, and the model of a row's source note. No React, no map.
import { METRIC_GROUPS, METRIC_INFO } from './metricInfo'
import { formatValue } from './metrics'

/** The areas a number can refer to, in the order of the chips and of the columns. */
export const AREAS = ['core', 'urban_centre', 'covered', 'fua']
/** Tram speed is a property of the city's network, not of an area; it is shown in every area view. */
export const TRAM_DOMAIN = 'city_tram_network'
/** Groups of the second, density-only table. */
export const DENSITY_GROUP_IDS = ['size', 'form', 'poly']

/** Short column heads of the cities, in the order of the comparison. Cities not listed come after, by catalog order. */
export const SHORT_CITY = {
  warszawa: 'Warszawa', krakow: 'Kraków', wroclaw: 'Wrocław', poznan: 'Poznań', lodz: 'Łódź', trojmiasto: 'Trójmiasto', gzm: 'GZM',
  bialystok: 'Białystok', bydgoszcz_torun: 'Bydg.–Toruń', kielce: 'Kielce', lublin: 'Lublin', rzeszow: 'Rzeszów',
  szczecin: 'Szczecin',
}
const CITY_ORDER = Object.keys(SHORT_CITY)

/** Metrics shown in the "inside" blocks of a city, not as rows of the main tables. */
export const TIME_OF_DAY = [
  { key: 'am', label: 'Szczyt poranny (7–9)', ids: { 30: 'tp_pt_am_30min', 45: 'tp_pt_am_45min' } },
  { key: 'midday', label: 'Południe', ids: { 30: 'tp_pt_midday_30min', 45: 'tp_pt_midday_45min' } },
  { key: 'evening', label: 'Wieczór', ids: { 30: 'tp_pt_evening_30min', 45: 'tp_pt_evening_45min' } },
  { key: 'saturday', label: 'Sobota', ids: { 30: 'tp_pt_saturday_30min', 45: 'tp_pt_saturday_45min' } },
]
const TIME_IDS = new Set(TIME_OF_DAY.flatMap((t) => Object.values(t.ids)))

export const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

/** {metric: {agglomeration: {domain: row}}}; rows of tier "qa" never get in, the first row of a key wins. */
export function indexMetrics(rows) {
  const idx = {}
  for (const r of rows || []) {
    if (r.tier === 'qa' || !r.metric || !r.agglomeration || !r.domain) continue
    const m = (idx[r.metric] ||= {})
    const a = (m[r.agglomeration] ||= {})
    if (!(r.domain in a)) a[r.domain] = r
  }
  return idx
}

/** The row of a metric for a city in an area; the tram network row stands in for any area. */
export function areaRow(index, id, agg, area) {
  const m = index[id]?.[agg]
  if (!m) return null
  return m[area] ?? m[TRAM_DOMAIN] ?? null
}

/** The row of a city's own table: the tram network sits in the first column only. */
export function cityCell(index, id, agg, area) {
  const m = index[id]?.[agg]
  if (!m) return null
  return m[area] ?? (area === AREAS[0] ? m[TRAM_DOMAIN] ?? null : null)
}

/** The value of a row, or null: a row without a number is "brak danych", never 0. */
export const valueOf = (row) => (row && isNum(row.value) ? row.value : null)

/**
 * Cities that have transport data: those with at least one row of a metric that is not a density/form one.
 * Ordered as SHORT_CITY, then any others by their order in `known` (the catalog's list).
 */
export function transportCities(index, known = [], groups = METRIC_GROUPS) {
  const densityOnly = new Set(groups.filter((g) => DENSITY_GROUP_IDS.includes(g.id)).flatMap((g) => g.metrics))
  const has = new Set()
  for (const [id, byAgg] of Object.entries(index)) {
    if (densityOnly.has(id)) continue
    for (const agg of Object.keys(byAgg)) has.add(agg)
  }
  return orderCities([...has], known)
}

/** All agglomerations that have any metric row. */
export function allCities(index, known = []) {
  const has = new Set()
  for (const byAgg of Object.values(index)) for (const agg of Object.keys(byAgg)) has.add(agg)
  return orderCities([...has], known)
}

function orderCities(ids, known) {
  const rank = (id) => {
    const i = CITY_ORDER.indexOf(id)
    if (i >= 0) return i
    const k = known.indexOf(id)
    return CITY_ORDER.length + (k >= 0 ? k : known.length)
  }
  return [...ids].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
}

/**
 * The groups of metrics a table shows: [{id, title, metrics: [ids]}], only ids that have a row in the index,
 * only groups that are left non-empty. Metrics in the file that no group lists come last, in the group "Inne
 * miary" (not the time-of-day ones, which have their own block). `onlyGroups` narrows to some group ids and
 * drops the leftovers.
 */
export function buildGroups(index, { groups = METRIC_GROUPS, onlyGroups = null } = {}) {
  const listed = new Set(groups.flatMap((g) => g.metrics))
  const out = groups
    .filter((g) => !onlyGroups || onlyGroups.includes(g.id))
    .map((g) => ({ id: g.id, title: g.title, metrics: g.metrics.filter((m) => index[m]) }))
  if (!onlyGroups) {
    const rest = Object.keys(index).filter((m) => !listed.has(m) && !TIME_IDS.has(m))
    out.push({ id: 'other', title: 'Inne miary', metrics: rest })
  }
  return out.filter((g) => g.metrics.length > 0)
}

/** Short name of a metric: the one in METRIC_INFO, else the label of any row, else the id. */
export function metricName(index, id, info = METRIC_INFO) {
  if (info[id]?.short) return info[id].short
  for (const byDomain of Object.values(index[id] || {})) {
    for (const r of Object.values(byDomain)) if (r.label) return r.label
  }
  return id
}

/** The unit of a metric (of its first row), or ''. */
export function metricUnit(index, id) {
  for (const byDomain of Object.values(index[id] || {})) {
    for (const r of Object.values(byDomain)) if (r.unit) return r.unit
  }
  return ''
}

/** "23,8" for a row: the formatted number without its unit, which the row heading carries. */
export function plainText(row) {
  const v = formatValue(row)
  if (v.missing) return null
  // the unit follows the number after a (non-breaking) space
  return row.unit && v.text.endsWith(row.unit) ? v.text.slice(0, -row.unit.length).trimEnd() : v.text
}

/**
 * Best and weakest cells of a row. `values` is a list of number|null in column order. Returns two Sets of
 * indices; both are empty when `better` is null/unknown, or fewer than three values exist, or all values are equal.
 * Ties share the mark.
 */
export function markExtremes(values, better) {
  const none = { best: new Set(), worst: new Set() }
  if (better !== 'higher' && better !== 'lower') return none
  const have = values.map((v, i) => [v, i]).filter(([v]) => isNum(v))
  if (have.length < 3) return none
  const nums = have.map(([v]) => v)
  const hi = Math.max(...nums)
  const lo = Math.min(...nums)
  if (hi === lo) return none
  const bestV = better === 'higher' ? hi : lo
  const worstV = better === 'higher' ? lo : hi
  return {
    best: new Set(have.filter(([v]) => v === bestV).map(([, i]) => i)),
    worst: new Set(have.filter(([v]) => v === worstV).map(([, i]) => i)),
  }
}

/** Rank (1 = best) of `value` among `values`; `better` null ranks high values first. Ties share the better rank. */
export function rankOf(values, value, better) {
  const nums = values.filter(isNum)
  if (!isNum(value)) return null
  const beats = better === 'lower' ? (v) => v < value : (v) => v > value
  return 1 + nums.filter(beats).length
}

/**
 * The area a metric is compared in: `prefer` when at least one city has a number there, else the first area
 * (then the tram network) that has one; null when no area has any.
 */
export function metricArea(index, id, cities, prefer = AREAS[0]) {
  for (const area of [...(AREA_NEAR[prefer] || [prefer, ...AREAS]), TRAM_DOMAIN]) {
    if (cities.some((c) => isNum(index[id]?.[c]?.[area]?.value))) return area
  }
  return null
}

/** For each area, the areas to try when it has no values: itself, then the nearest in meaning. */
export const AREA_NEAR = {
  core: ['core', 'urban_centre', 'covered', 'fua'],
  urban_centre: ['urban_centre', 'core', 'covered', 'fua'],
  covered: ['covered', 'fua', 'core', 'urban_centre'],
  fua: ['fua', 'covered', 'core', 'urban_centre'],
}

/**
 * The area to read a metric in when the page asks for `area`: that one when any of `cities` has a value there, else the
 * nearest that has (`moved: true`, so the caller says so). A metric that exists only as a tram-network row (no area at all)
 * stays on `area`: those rows stand in for every area.
 */
export function resolveRowArea(index, id, cities, area) {
  for (const a of AREA_NEAR[area] || [area]) {
    if (cities.some((c) => isNum(index[id]?.[c]?.[a]?.value))) return { area: a, moved: a !== area }
  }
  return { area, moved: false }
}

/**
 * Rank of a city among the cities that have the metric, in the area the row is read in: {rank, n, area, moved} or null
 * when the metric has no direction (a rank would mean nothing), the city has no value, or fewer than three cities have
 * one. `pool` is the cities to rank among (all agglomerations): n is how many of them have the metric (7 or 13).
 */
export function rankAmong(index, id, pool, agg, area, better) {
  if (better !== 'higher' && better !== 'lower') return null
  const r = resolveRowArea(index, id, pool, area)
  const vals = pool.map((c) => valueOf(areaRow(index, id, c, r.area)))
  const mine = valueOf(areaRow(index, id, agg, r.area))
  const n = vals.filter(isNum).length
  if (mine == null || n < 3) return null
  return { rank: rankOf(vals, mine, better), n, area: r.area, moved: r.moved }
}

/**
 * Where a city stands in a metric among `cities`: {area, rank, n, count, first, last} or null (no value for the
 * city, or fewer than three cities with one). `first` / `last` are true only for a rank held by that city alone.
 */
export function standing(index, id, cities, agg, better, prefer = AREAS[0]) {
  const area = metricArea(index, id, cities, prefer)
  if (!area) return null
  const vals = cities.map((c) => valueOf(index[id]?.[c]?.[area]))
  const mine = valueOf(index[id]?.[agg]?.[area])
  const n = vals.filter(isNum).length
  if (mine == null || n < 3) return null
  const rank = rankOf(vals, mine, better)
  const tied = vals.filter((v) => v === mine).length > 1
  return { area, rank, n, first: rank === 1 && !tied, last: rank === n && !tied, value: mine }
}

const COUNT_WORD = { 3: 'trzech', 4: 'czterech', 5: 'pięciu', 6: 'sześciu', 7: 'siedmiu', 8: 'ośmiu', 9: 'dziewięciu', 10: 'dziesięciu' }

/**
 * Up to `max` statements about what sets `agg` apart: metrics (with a direction of better) where it is alone
 * first or last among `cities`, in the order of the groups, e.g.
 * "Najwyższa wśród siedmiu miast: Zasięg komunikacją w 30 min (31,6 %)".
 */
export function highlights(index, cities, agg, { max = 4, groups = METRIC_GROUPS, info = METRIC_INFO, area = AREAS[0], transport = null } = {}) {
  const out = []
  for (const g of buildGroups(index, { groups })) {
    for (const id of g.metrics) {
      const better = info[id]?.better
      if (better !== 'higher' && better !== 'lower') continue
      const s = standing(index, id, cities, agg, better, area)
      if (!s || !(s.first || s.last)) continue
      // the highest value is first for "higher", last for "lower"
      const highest = (s.first && better === 'higher') || (s.last && better === 'lower')
      const row = index[id][agg][s.area]
      const word = COUNT_WORD[s.n] || String(s.n)
      // the seven with timetables are named as such; the whole set as "aglomeracji"
      const among = transport && s.n === transport.length && transport.every((c) => cities.includes(c))
        ? `wśród ${word} miast z danymi o transporcie` : s.n === cities.length ? `wśród ${s.n} aglomeracji` : `wśród ${word} miast`
      out.push(`${highest ? 'Najwyższa' : 'Najniższa'} ${among}: ${metricName(index, id, info)} (${formatValue(row).text})`)
      if (out.length >= max) return out
    }
  }
  return out
}

/**
 * Rows of the "Pora dnia" block for a city: [{key, label, v30, v45}] with number|null values (core area). The block
 * exists only when a time-of-day metric other than the morning peak has arrived in the data; otherwise null.
 */
export function timeOfDay(index, agg, area = AREAS[0]) {
  const rows = TIME_OF_DAY.map((t) => ({
    key: t.key, label: t.label,
    v30: valueOf(index[t.ids[30]]?.[agg]?.[area]), v45: valueOf(index[t.ids[45]]?.[agg]?.[area]),
    unit: index[t.ids[30]]?.[agg]?.[area]?.unit || index[t.ids[45]]?.[agg]?.[area]?.unit || '%',
  })).filter((r) => r.v30 != null || r.v45 != null)
  return rows.some((r) => r.key !== 'am') ? rows : null
}

const CENTRE = /^(hub_1km|centre_1km)(_.+)?$/

/** Rows of the "Z centrów" block: [{domain, label, v30, v45, unit}] for domains hub_1km, centre_1km, centre_1km_<name>. */
export function centreRows(index, agg) {
  const domains = new Set()
  for (const id of ['tp_pt_am_30min', 'tp_pt_am_45min']) {
    for (const d of Object.keys(index[id]?.[agg] || {})) if (CENTRE.test(d)) domains.add(d)
  }
  const coreLabel = index.tp_pt_am_30min?.[agg]?.core?.label
  return [...domains].map((domain) => {
    const r30 = index.tp_pt_am_30min?.[agg]?.[domain]
    const r45 = index.tp_pt_am_45min?.[agg]?.[domain]
    const own = r30?.label || r45?.label
    return {
      domain,
      label: own && own !== coreLabel ? own : domain,
      v30: valueOf(r30), v45: valueOf(r45), unit: r30?.unit || r45?.unit || '%',
    }
  }).filter((r) => r.v30 != null || r.v45 != null)
}

/** What to say about where a row's numbers come from: one note for the row, from the rows of its cells. */
export function sourceModel(entries, { feedNames = {}, nameOf = (x) => x } = {}) {
  // entries: [{key, row}] with row possibly null
  const rows = entries.filter((e) => e.row)
  if (!rows.length) return { source: null, dates: [], feed: null, coverage: [], flags: [] }
  const first = rows[0].row
  const dates = []
  if (first.population_date) dates.push(`ludność: ${first.population_date}`)
  if (first.timetable_date) dates.push(`rozkłady: ${first.timetable_date}`)
  const feed = first.feed_variant ? (feedNames[first.feed_variant] || first.feed_variant) : null
  const coverage = rows.filter((e) => isNum(e.row.coverage_share))
    .map((e) => ({ key: nameOf(e.key), share: e.row.coverage_share }))
  const byText = new Map()
  for (const e of rows) {
    if (!e.row.flag) continue
    if (!byText.has(e.row.flag)) byText.set(e.row.flag, [])
    byText.get(e.row.flag).push(nameOf(e.key))
  }
  const flags = [...byText].map(([text, keys]) => ({ text, keys: keys.length === rows.length && rows.length > 1 ? [] : keys }))
  return { source: first.source || null, dates, feed, coverage, flags }
}

// ---- busiest stop areas -------------------------------------------------------------------------------------

/** "dojście 1,2 min, czekanie 4,5 min"; null when the node has neither. Uses the weighted walk_w/wait_w when present. */
export function nodeSub(p) {
  const f = (v) => new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1 }).format(v)
  const useW = isNum(p.walk_w) && isNum(p.wait_w)
  const walk = useW ? p.walk_w : p.walk_dir
  const wait = useW ? p.wait_w : p.wait_am
  const parts = []
  if (isNum(walk)) parts.push(`dojście ${f(walk)} min`)
  if (isNum(wait)) parts.push(`czekanie ${f(wait)} min`)
  return parts.length ? parts.join(', ') : null
}

/** The `n` nodes of an agglomeration with the most departures per hour (dep_h): [{id, name, dep, sub, coordinates, props}]. */
export function topNodes(features, agg, n = 8, by = 'dep') {
  const key = by === 'use' ? 'use' : 'dep_h'
  return (features || [])
    .filter((f) => f?.properties?.agg === agg && isNum(f.properties[key]) && f.geometry?.type === 'Point' && (by !== 'use' || f.properties.use_ok))
    .sort((a, b) => b.properties[key] - a.properties[key])
    .slice(0, n)
    .map((f) => ({
      id: f.properties.id ?? `${f.geometry.coordinates.join(',')}`,
      name: f.properties.name || 'Zespół przystanków',
      dep: f.properties.dep_h,
      use: isNum(f.properties.use) ? f.properties.use : null,
      detail: !!f.properties.detail,
      sub: nodeSub(f.properties),
      coordinates: f.geometry.coordinates,
      props: f.properties,
    }))
}

/** The measures a city's first tab leads with, in order of preference (the first six the city has are shown). */
export const HEADLINE_IDS = [
  'tp_pt_am_30min_ratio_of_means', 'freq_seg_net_le10min', 'dist_below_floor_pt_am_30min', 'vkm_per_cap_day_total',
  'rail_ge4dph_net_1km', 'pwdens_census_1km', 'share_residents_ge5000', 'median_resident_density_250m', 'population_census', 'area',
]

/**
 * Up to `max` headline numbers of a city in `area`: [{id, name, text, rank: {rank, n} | null, moved, area}], text being the
 * value with its unit. Measures the city has no value for are skipped, so a city with density only gets density figures.
 */
export function headlineRows(index, pool, agg, area, { max = 6, info = METRIC_INFO } = {}) {
  const out = []
  for (const id of HEADLINE_IDS) {
    if (!index[id]?.[agg]) continue
    const at = resolveRowArea(index, id, [agg], area)
    const row = areaRow(index, id, agg, at.area)
    if (valueOf(row) == null) continue
    const st = rankAmong(index, id, pool, agg, area, info[id]?.better)
    out.push({ id, name: metricName(index, id, info), text: formatValue(row).text, rank: st ? { rank: st.rank, n: st.n } : null, moved: at.moved, area: at.area })
    if (out.length >= max) break
  }
  return out
}
