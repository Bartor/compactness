// What the table builder is asked for, and what that makes: the pure logic of the configurable table. The state is
//   {set, ids, cities, areas, swap}
// set    'n' (Najważniejsze, the default), 'all', the id of a group of METRIC_GROUPS, or 'own' (a hand-made list in `ids`)
// cities null (the default of the view) | 'tt' (the cities with timetables) | 'all' | [city ids]
// areas  null (follow the header's switch) | [area keys]
// swap   rows and columns exchanged, where both a city and an area dimension have several values
// No React here.
import { METRIC_GROUPS } from '../../metricInfo'
import { AREAS, buildGroups } from '../../metricTable'

/** The measures that tell the story, in the order the table shows them (a preset is not grouped, so the order is this). */
export const NAJWAZNIEJSZE = [
  'population_census', 'pwdens_census_1km', 'tp_pt_am_30min_ratio_of_means', 'freq_seg_net_le10min',
  'dist_below_floor_pt_am_30min', 'tram_speed_median', 'vkm_per_cap_day_total', 'transfer_top20_walkwait_w_am_mean_min',
  'dxs_dense_underserved_share', 'svc_school_pt_am_le30min',
]

export const SET_STORY = 'n'
export const SET_ALL = 'all'
export const SET_OWN = 'own'
export const DEFAULT_TABLE = { set: SET_STORY, ids: [], cities: null, areas: null, swap: false }

/** The presets in the order of the chips: [{id, title}]; the groups come from METRIC_GROUPS. */
export const PRESET_GROUPS = METRIC_GROUPS.map((g) => ({ id: g.id, title: g.title }))
const PRESET_IDS = new Set([SET_STORY, SET_ALL, ...PRESET_GROUPS.map((g) => g.id)])
export const isPreset = (id) => PRESET_IDS.has(id)

export const presetTitle = (set) => (set === SET_STORY ? 'Najważniejsze' : set === SET_ALL ? 'Wszystkie' : set === SET_OWN ? 'Własny'
  : PRESET_GROUPS.find((g) => g.id === set)?.title || '')

const isList = (x) => Array.isArray(x)
const uniq = (xs) => [...new Set(xs)]

/** A state with anything odd (an old link, a bad value) replaced by the default for that part. */
export function normalizeTable(t) {
  const x = t || {}
  const set = x.set === SET_OWN || isPreset(x.set) ? x.set : SET_STORY
  const areas = isList(x.areas) ? AREAS.filter((a) => x.areas.includes(a)) : null
  const cities = isList(x.cities) ? uniq(x.cities.filter((c) => typeof c === 'string' && c)) : x.cities === 'tt' || x.cities === 'all' ? x.cities : null
  return {
    set,
    ids: set === SET_OWN && isList(x.ids) ? uniq(x.ids.filter((i) => typeof i === 'string' && i)) : [],
    cities: isList(cities) && cities.length === 0 ? null : cities,
    areas: areas && areas.length ? areas : null,
    swap: !!x.swap,
  }
}

// ---- which measures ------------------------------------------------------------------------------------------

/**
 * The measures a state asks for, those that exist in the data: {groups: [{id, title, metrics}], flat, ids}. The story
 * preset is one list in its own order (`flat`: no group headings); everything else follows the groups of the data.
 */
export function selectionOf(table, index) {
  const all = buildGroups(index)
  const have = new Set(all.flatMap((g) => g.metrics))
  let groups
  let flat = false
  if (table.set === SET_STORY) {
    groups = [{ id: SET_STORY, title: 'Najważniejsze', metrics: NAJWAZNIEJSZE.filter((id) => have.has(id)) }]
    flat = true
  } else if (table.set === SET_ALL) groups = all
  else if (table.set === SET_OWN) {
    const want = new Set(table.ids)
    groups = all.map((g) => ({ ...g, metrics: g.metrics.filter((id) => want.has(id)) }))
  } else groups = all.filter((g) => g.id === table.set)
  groups = groups.filter((g) => g.metrics.length > 0)
  return { groups, flat: flat || groups.length === 1, ids: groups.flatMap((g) => g.metrics) }
}

/** True when a measure exists for none of `rest` (the cities without timetables): it needs the timetables. */
export const needsTimetable = (index, id, rest) => !rest.some((c) => index[id]?.[c])

// ---- which cities --------------------------------------------------------------------------------------------

/**
 * The cities of the table, in the order of `everyCity`: [agg] in a city's view unless the reader chose others; in the
 * comparison the cities with timetables when a chosen measure needs them (all of them for "Wszystkie", as the table was),
 * else everything.
 */
export function citiesOf(table, { agg = null, everyCity, transport, index, ids }) {
  const known = (list) => everyCity.filter((c) => list.includes(c))
  if (isList(table.cities)) {
    const picked = known(table.cities)
    if (picked.length) return picked
  }
  if (table.cities === 'tt') return known(transport)
  if (table.cities === 'all') return [...everyCity]
  if (agg) return [agg]
  if (table.set === SET_ALL) return [...everyCity]
  const rest = everyCity.filter((c) => !transport.includes(c))
  return ids.some((id) => needsTimetable(index, id, rest)) ? known(transport) : [...everyCity]
}

/** Which of the chips of the cities is on: 'own' (the city of the view), 'tt', 'all' or 'pick'. */
export function citiesMode(cities, { agg, everyCity, transport }) {
  const same = (a, b) => a.length === b.length && a.every((x) => b.includes(x))
  if (agg && cities.length === 1 && cities[0] === agg) return 'own'
  if (same(cities, everyCity)) return 'all'
  if (same(cities, everyCity.filter((c) => transport.includes(c)))) return 'tt'
  return 'pick'
}

// ---- which areas ---------------------------------------------------------------------------------------------

/** The areas of the table: the reader's, else the header's area. One city in one area is the value with its rank
 *  among the cities, which is what a city's view opens with; the other areas are one click away. */
export function areasOf(table, { globalArea }) {
  if (table.areas) return { areas: table.areas, following: false }
  return { areas: [globalArea], following: true }
}

/** The next list of areas after a click on `area`: toggled in `current`, never empty (an empty list means "follow"). */
export function toggleArea(current, area) {
  const next = current.includes(area) ? current.filter((a) => a !== area) : AREAS.filter((a) => a === area || current.includes(a))
  return next.length ? next : null
}

// ---- the shape -----------------------------------------------------------------------------------------------

/**
 * How the table is laid out for `cities` x `areas`: {key, cols, sub, canSwap}. `cols` is what the columns are ('cities',
 * 'areas', or 'value' for one city in one area: the value and its rank); `sub` the dimension that makes sub-rows under
 * each measure ('area', 'city' or null).
 */
export function shapeOf(cities, areas, swap = false) {
  const canSwap = cities.length > 1 && areas.length > 1
  if (canSwap) return swap ? { key: 'subcity', cols: 'areas', sub: 'city', canSwap } : { key: 'subarea', cols: 'cities', sub: 'area', canSwap }
  if (cities.length > 1) return { key: 'cities', cols: 'cities', sub: null, canSwap }
  if (areas.length > 1) return { key: 'areas', cols: 'areas', sub: null, canSwap }
  return { key: 'value', cols: 'value', sub: null, canSwap }
}

/** The key of a sub-row: the measure and the area (or city) it is read in. A sort of a plain row is the plain id. */
export const subKey = (id, part) => `${id}~${part}`
export const subKeyMeasure = (key) => String(key).split('~')[0]

// ---- the address -----------------------------------------------------------------------------------------------

const LIST = ','

/** What the address says about the table: {set, ids, cities, areas, swap} with only the parts that were given, or null. */
export function parseTableKeys(q) {
  const has = ['tb', 'tc', 'ta', 'tx'].some((k) => q.has(k))
  if (!has) return null
  const out = {}
  if (q.has('tb')) {
    const parts = q.get('tb').split(LIST).filter(Boolean)
    if (parts.length === 1 && isPreset(parts[0])) out.set = parts[0]
    else { out.set = SET_OWN; out.ids = parts }
  }
  if (q.has('tc')) {
    const v = q.get('tc')
    out.cities = v === 'tt' || v === 'all' ? v : v.split(LIST).filter(Boolean)
  }
  if (q.has('ta')) out.areas = q.get('ta').split(LIST).filter((a) => AREAS.includes(a))
  if (q.get('tx') === '1') out.swap = true
  return out
}

/** Writes the table's keys into URLSearchParams `q`; only what differs from the default. */
export function writeTableKeys(q, table) {
  const t = normalizeTable(table)
  if (t.set === SET_OWN) q.set('tb', t.ids.join(LIST))
  else if (t.set !== SET_STORY) q.set('tb', t.set)
  if (isList(t.cities)) q.set('tc', t.cities.join(LIST))
  else if (t.cities) q.set('tc', t.cities)
  if (t.areas) q.set('ta', t.areas.join(LIST))
  if (t.swap) q.set('tx', '1')
}

/** The state from what the address gave (unknown ids stay: they are dropped where they meet the data). */
export const tableFromKeys = (keys) => normalizeTable({ ...DEFAULT_TABLE, ...(keys || {}) })
