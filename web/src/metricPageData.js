// Pure logic of the metric page (one metric for all cities): which areas and cities it has, the order of the table
// to walk with "previous / next", which related charts a metric gets, the page's prose from METRIC_INFO, the
// distinct sources of its rows and the density-class bars from form.json. No React.
import { METRIC_INFO } from './metricInfo'
import { FEED_VARIANTS, POPULATION_GRIDS } from './metrics'
import { AREAS, TRAM_DOMAIN, buildGroups, isNum, valueOf } from './metricTable'

/** Every area a number can refer to, in the order of the chips. */
export const PAGE_AREAS = [...AREAS, TRAM_DOMAIN]

/** The areas in which at least one city has a number for the metric, in chip order. */
export function pageAreas(index, id) {
  return PAGE_AREAS.filter((a) => Object.values(index[id] || {}).some((byDomain) => isNum(byDomain[a]?.value)))
}

/** The area to show: the one asked for when the metric has it, else the core city, else the first it has; null for none. */
export function pickArea(index, id, wanted) {
  const have = pageAreas(index, id)
  if (have.includes(wanted)) return wanted
  return have.includes('core') ? 'core' : have[0] ?? null
}

/** Cities the page lists: all agglomerations when any city beyond those with transport data has the metric, else the transport ones. */
export function universe(index, id, everyCity, transportCities) {
  const has = (c) => Object.values(index[id]?.[c] || {}).some((r) => isNum(r?.value))
  return everyCity.some((c) => !transportCities.includes(c) && has(c)) ? everyCity : transportCities
}

/** {have: [{id, value, row}], missing: [id]} of `cities` for a metric in an area (no stand-in rows: a missing value is missing). */
export function cityValues(index, id, area, cities) {
  const have = []
  const missing = []
  for (const c of cities) {
    const row = index[id]?.[c]?.[area] ?? null
    const value = valueOf(row)
    if (value == null) missing.push(c)
    else have.push({ id: c, value, row })
  }
  return { have, missing }
}

/** The median of the numbers (null for none). */
export function medianOf(values) {
  const a = values.filter(isNum).sort((p, q) => p - q)
  if (!a.length) return null
  const m = a.length >> 1
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2
}

/** Rank (1 = best) of every city in `have`: by `better` ('lower' ascending, anything else descending); ties share the better rank. */
export function ranks(have, better) {
  const out = {}
  for (const h of have) out[h.id] = 1 + have.filter((o) => (better === 'lower' ? o.value < h.value : o.value > h.value)).length
  return out
}

/** The metrics in the order of the tables: [{id, group, groupTitle}], across groups. */
export function walkOrder(index) {
  return buildGroups(index).flatMap((g) => g.metrics.map((id) => ({ id, group: g.id, groupTitle: g.title })))
}

/** Where `id` is in the walk: {prev, next (ids or null), group, groupTitle, position, total}; null for an unknown metric. */
export function neighbours(order, id) {
  const i = order.findIndex((o) => o.id === id)
  if (i < 0) return null
  return {
    prev: i > 0 ? order[i - 1].id : null, next: i < order.length - 1 ? order[i + 1].id : null,
    group: order[i].group, groupTitle: order[i].groupTitle, position: i + 1, total: order.length,
  }
}

const REACH = /^tp_(pt_am|walk|bike_lts3|bike_lts4)_(30|45)min$/
const DIST = /^dist_(below_floor|fgt1|p25|p75)_pt_(am|evening|saturday)_(30|45)min$/
const DENSITY_METRICS = ['share_residents_ge5000', 'median_resident_density_250m']

/** The base id of a reach metric ("..._ratio_of_means" is the headline of the one without the suffix). */
export const reachBase = (id) => id.replace(/_ratio_of_means$/, '')

/**
 * The related blocks of a metric, in order, as descriptors for the page to resolve against the data it has:
 *   twin        the headline (ratio of means) and the typical-resident row of the same measure
 *   pair30v45   the same measure at 30 and at 45 minutes
 *   atleast     the "at least x" curve of a series (pt_am_30 ...), with the access floor when `floor` is 30 or 45
 *   reach       the reach curve of a mode (pt_am, walk, bike_lts3, bike_lts4)
 *   timeofday   the time-of-day chart
 *   headway     the headway curve
 *   dumbbell    a paired chart of the charts file (`pair`)
 *   density     residents by density class per city (form.json)
 */
export function relatedBlocks(id) {
  const out = []
  const m = REACH.exec(reachBase(id))
  if (m) {
    const [, mode, cut] = m
    out.push({ type: 'twin' }, { type: 'pair30v45' })
    out.push({ type: 'atleast', series: `${mode}_${cut}`, floor: null })
    out.push({ type: 'reach', mode })
    if (mode === 'pt_am') out.push({ type: 'timeofday' })
  }
  if (/^freq_seg_net_le\d+min$/.test(id)) out.push({ type: 'headway' })
  const d = DIST.exec(id)
  if (d) {
    out.push({ type: 'atleast', series: `pt_am_${d[3]}`, floor: Number(d[3]) })
    if (d[1] === 'below_floor') out.push({ type: 'dumbbell', pair: 'peak_evening_floor' })
  }
  if (DENSITY_METRICS.includes(id)) out.push({ type: 'density' })
  return out
}

/** The id of the row paired with `id` for a pair, or null: 'twin' (headline <-> typical) and 'pair30v45' (30 <-> 45 min). */
export function partnerOf(id, kind) {
  if (kind === 'twin') return id.endsWith('_ratio_of_means') ? { a: id, b: reachBase(id), aLabel: 'wskaźnik porównawczy', bLabel: 'typowy mieszkaniec' }
    : { a: `${id}_ratio_of_means`, b: id, aLabel: 'wskaźnik porównawczy', bLabel: 'typowy mieszkaniec' }
  if (kind === 'pair30v45') {
    const suffix = id.endsWith('_ratio_of_means') ? '_ratio_of_means' : ''
    const base = reachBase(id)
    if (base.includes('_30min')) return { a: id, b: `${base.replace('_30min', '_45min')}${suffix}`, aLabel: '30 min', bLabel: '45 min' }
    if (base.includes('_45min')) return { a: `${base.replace('_45min', '_30min')}${suffix}`, b: id, aLabel: '30 min', bLabel: '45 min' }
  }
  return null
}

const UNCERTAINTY_START = 'Niepewność'

/**
 * The prose of a metric page from METRIC_INFO: {lead, read, uncertainty, method, gaps}. `lead` is the first paragraph
 * of "jak czytać" (set in large type), `read` the others, `uncertainty` the sentences that start with "Niepewność",
 * `method` "jak policzono". `gaps` lists what the metric has no text for.
 */
export function pageText(id, info = METRIC_INFO) {
  const i = info[id]
  const read = (i?.read || []).filter((p) => !p.startsWith(UNCERTAINTY_START))
  const uncertainty = (i?.read || []).filter((p) => p.startsWith(UNCERTAINTY_START))
  const method = i?.method || []
  const gaps = []
  if (!i) gaps.push('opis miary')
  else {
    if (!read.length) gaps.push('jak czytać')
    if (!method.length) gaps.push('jak policzono')
  }
  return { lead: read[0] || null, read: read.slice(1), uncertainty, method, gaps }
}

/** The badge for the direction of a metric. */
export function directionBadge(better) {
  if (better === 'higher') return 'wyżej = lepiej'
  if (better === 'lower') return 'niżej = lepiej'
  return null
}

const nf0 = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 })

/**
 * Where the numbers of a metric come from, from the rows themselves: [{label, values: [text]}], each distinct value
 * once, in a fixed order, only for fields that some row carries.
 */
export function sourceFacts(rows) {
  const rs = rows.filter(Boolean)
  const uniq = (get) => [...new Set(rs.map(get).filter((v) => v != null && v !== ''))]
  const facts = [
    { label: 'Źródło', values: uniq((r) => r.source) },
    { label: 'Dane o ludności', values: uniq((r) => (r.population_grid ? POPULATION_GRIDS[r.population_grid] || r.population_grid : r.grid)) },
    { label: 'Data danych o ludności', values: uniq((r) => r.population_date) },
    { label: 'Wersja rozkładów jazdy', values: uniq((r) => (r.feed_variant ? FEED_VARIANTS[r.feed_variant] || r.feed_variant : null)) },
    { label: 'Data rozkładów jazdy', values: uniq((r) => r.timetable_date) },
    { label: 'Pokrycie danymi o rozkładach', values: uniq((r) => (isNum(r.coverage_share) ? `${nf0.format(r.coverage_share * 100)} %` : null)).sort() },
    { label: 'Uwagi', values: uniq((r) => r.flag) },
  ]
  return facts.filter((f) => f.values.length > 0)
}

/** Every row of a metric in the index (all cities, all areas). */
export const rowsOf = (index, id) => Object.values(index[id] || {}).flatMap((byDomain) => Object.values(byDomain))

/**
 * Bars of residents by density class per city from form.json: [{key, label, parts: [{key, label, color, share}]}] in the
 * order of `cities` (ids), cities missing from the file skipped. `area` 'core' reads the core city, anything else the
 * whole functional area (the file has no more); `colors` are the classes' colours in order (the map's density ramp).
 */
export function densityBars(form, cities, area, colors) {
  if (!form?.cities || !form?.classes) return []
  const dom = area === 'core' ? 'core' : 'fua'
  const byId = Object.fromEntries(form.cities.map((c) => [c.id, c]))
  return cities.filter((c) => byId[c]?.[dom]?.share).map((c) => ({
    key: c,
    label: byId[c].name || c,
    parts: form.classes.map((cl, k) => ({ key: String(k), label: cl.label, color: colors?.[k] || '#888', share: byId[c][dom].share[k] ?? 0 })),
  }))
}

/** The address part of an open page: {id, area} from the hash fields `m` and `ma`; null for none. */
export function pageFromHash(m, ma, index) {
  if (!m || !index[m]) return null
  return { id: m, area: pickArea(index, m, ma) }
}
