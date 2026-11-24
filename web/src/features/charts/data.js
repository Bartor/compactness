// Loader and pure selectors for data/charts.json (written by pipeline.distribution as results/web/charts.json).
// No app imports: the base URL is a parameter.

import { median } from './scales'

export const CITY_ORDER = ['warszawa', 'krakow', 'wroclaw', 'poznan', 'lodz', 'trojmiasto', 'gzm']
export const WINDOWS = ['pt_am', 'pt_midday', 'pt_evening', 'pt_saturday']
export const DOMAIN_LABEL = { core: 'rdzeń', covered: 'obszar pokryty', urban_centre: 'centrum miejskie' }

/**
 * Fetch charts.json. Optional data: any failure resolves to null (the caller hides the charts), never throws.
 * @param {{base?: string, fetchImpl?: typeof fetch}} opts  base defaults to './data/' (the site's data folder)
 */
export async function loadCharts({ base = './data/', fetchImpl = globalThis.fetch } = {}) {
  try {
    const res = await fetchImpl(base + 'charts.json')
    if (!res.ok) return null
    const j = await res.json()
    return j && typeof j === 'object' && j.cities ? j : null
  } catch {
    return null
  }
}

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/** The domain object of one city, or null. */
export function cityDomain(charts, agg, domain = 'core') {
  return charts?.cities?.[agg]?.domains?.[domain] || null
}

/** Cities present in the file, in the fixed order (colour follows the city, never its rank). */
export function cityIds(charts) {
  const have = Object.keys(charts?.cities || {})
  return [...CITY_ORDER.filter((a) => have.includes(a)), ...have.filter((a) => !CITY_ORDER.includes(a)).sort()]
}

export const cityName = (charts, agg) => charts?.cities?.[agg]?.name || agg

/** "At least x" curves: one series per city. series: pt_am_30 | pt_am_45 | walk_30 | bike_lts3_30 | bike_lts4_30. */
export function atLeastSeries(charts, { aggs, domain = 'core', series = 'pt_am_30' } = {}) {
  const xs = charts?.x_performance || []
  return (aggs || cityIds(charts)).map((agg) => ({
    key: agg, label: cityName(charts, agg), xs,
    ys: cityDomain(charts, agg, domain)?.at_least?.[series] || null,
  }))
}

/** Headway curve: share of residents with service at least every N minutes (N = 5, 10, 15, 20, 30). */
export function headwaySeries(charts, { aggs, domain = 'core' } = {}) {
  const xs = charts?.headway_n_min || []
  return (aggs || cityIds(charts)).map((agg) => ({
    key: agg, label: cityName(charts, agg), xs,
    ys: cityDomain(charts, agg, domain)?.headway_at_most || null,
  }))
}

/** Reach curve 5-60 min with the quartile band. mode: pt_am | walk | bike_lts3 | bike_lts4. */
export function reachSeries(charts, { aggs, domain = 'core', mode = 'pt_am' } = {}) {
  const xs = charts?.cutoffs_min || []
  return (aggs || cityIds(charts)).map((agg) => {
    const r = cityDomain(charts, agg, domain)?.reach?.[mode]
    return { key: agg, label: cityName(charts, agg), xs,
      rom: r?.ratio_of_means || null, mor: r?.mean_of_ratios || null,
      p25: r?.p25 || null, p50: r?.p50 || null, p75: r?.p75 || null }
  })
}

/** One-number measures for DotStrip, read from a domain object. */
export const MEASURES = {
  below_floor_30: { label: 'Mieszkańcy poniżej minimalnego zasięgu, 30 min', unit: '%', better: 'low',
    get: (d) => d?.floor?.['30']?.below_floor },
  below_floor_45: { label: 'Mieszkańcy poniżej minimalnego zasięgu, 45 min', unit: '%', better: 'low',
    get: (d) => d?.floor?.['45']?.below_floor },
  fgt1_30: { label: 'Średni niedobór do progu, 30 min (FGT1 × 100)', unit: '% progu', better: 'low',
    get: (d) => d?.floor?.['30']?.fgt1 },
  rom_30: { label: 'Zasięg komunikacją + pieszo, 30 min (7–9)', unit: '%', better: 'high',
    get: (d) => d?.time_of_day?.pt_am_30?.ratio_of_means },
  rom_45: { label: 'Zasięg komunikacją + pieszo, 45 min (7–9)', unit: '%', better: 'high',
    get: (d) => d?.time_of_day?.pt_am_45?.ratio_of_means },
  p50_30: { label: 'Mediana zasięgu mieszkańców, 30 min', unit: '%', better: 'high',
    get: (d) => d?.time_of_day?.pt_am_30?.p50 },
  headway_le10: { label: 'Mieszkańcy z kursami co ≤ 10 min', unit: '%', better: 'high',
    get: (d) => d?.headway_at_most?.[1] },
  palma_30: { label: 'Wskaźnik Palmy, 30 min', unit: '', better: 'low', get: (d) => d?.palma?.['30'] },
}

/** Rows for DotStrip: one per city, plus the seven-city median. */
export function dotStripRows(charts, { measure = 'below_floor_30', domain = 'core' } = {}) {
  const m = MEASURES[measure]
  const rows = cityIds(charts).map((agg) => ({ key: agg, label: cityName(charts, agg),
    value: num(m?.get(cityDomain(charts, agg, domain))) }))
  return { rows, median: median(rows.map((r) => r.value)), label: m?.label || measure, unit: m?.unit ?? '%' }
}

/** Paired conditions for Dumbbell. Each: labels of the two ends and a getter (charts, agg) -> [a, b]. */
export const PAIRS = {
  '30v45': { label: 'Zasięg 30 i 45 min (7–9, rdzeń)', a: '30 min', b: '45 min', unit: '%',
    get: (c, agg) => [MEASURES.rom_30.get(cityDomain(c, agg, 'core')), MEASURES.rom_45.get(cityDomain(c, agg, 'core'))] },
  peak_evening: { label: 'Zasięg 30 min: szczyt poranny i wieczór (rdzeń)', a: '7–9', b: 'wieczór', unit: '%',
    get: (c, agg) => {
      const t = cityDomain(c, agg, 'core')?.time_of_day
      return [t?.pt_am_30?.ratio_of_means, t?.pt_evening_30?.ratio_of_means]
    } },
  peak_evening_floor: { label: 'Poniżej minimalnego zasięgu 30 min: szczyt i wieczór (rdzeń)', a: '7–9', b: 'wieczór', unit: '%',
    get: (c, agg) => {
      const t = cityDomain(c, agg, 'core')?.time_of_day
      return [t?.pt_am_30?.below_floor, t?.pt_evening_30?.below_floor]
    } },
  core_uc: { label: 'Zasięg 30 min: rdzeń i centrum miejskie', a: 'rdzeń', b: 'centrum miejskie', unit: '%',
    get: (c, agg) => [MEASURES.rom_30.get(cityDomain(c, agg, 'core')), MEASURES.rom_30.get(cityDomain(c, agg, 'urban_centre'))] },
}

export function dumbbellRows(charts, pair = '30v45') {
  const p = PAIRS[pair]
  const rows = cityIds(charts).map((agg) => {
    const [a, b] = p ? p.get(charts, agg) : [null, null]
    return { key: agg, label: cityName(charts, agg), a: num(a), b: num(b) }
  })
  return { rows, label: p?.label || pair, aLabel: p?.a || 'a', bLabel: p?.b || 'b', unit: p?.unit ?? '%' }
}

/** Time of day for one city: rows per window with the 30 and 45 min values of one measure. */
export function timeOfDayRows(charts, { agg, domain = 'core', measure = 'ratio_of_means' } = {}) {
  const t = cityDomain(charts, agg, domain)?.time_of_day || {}
  const names = charts?.windows || {}
  return WINDOWS.map((w) => ({ key: w, label: names[w] || w,
    v30: num(t[`${w}_30`]?.[measure]), v45: num(t[`${w}_45`]?.[measure]) }))
}

/**
 * Class limits of a map layer to draw on the matching chart, from charts.layer_marks:
 * {series: 'pt_am_30' | 'headway', stops: [..]} or null when the layer has no chart.
 */
export function layerMarks(charts, layerId) {
  return charts?.layer_marks?.[layerId] || null
}

/** The access floor used for one cutoff (30 or 45). */
export function floorOf(charts, cutoff = 30) {
  const f = charts?.floor
  return num(f?.floors?.[String(cutoff)]?.[String(f?.main_fraction ?? 0.5)])
}
