// Pure helpers for the metrics table: grouping and formatting.
// A null value is "brak danych", never a zero.
export const NO_DATA = 'brak danych'

export const DOMAIN_TITLES = {
  fua: 'Cały obszar FUA',
  core: 'Rdzeń miasta',
  covered: 'Obszar pokryty danymi GTFS',
  city_tram_network: 'Sieć tramwajowa miasta',
}
const DOMAIN_ORDER = ['fua', 'core', 'covered', 'city_tram_network']

export const FEED_VARIANTS = { all: 'wszystkie feedy, w tym nieoficjalne', official: 'feedy oficjalne' }
export const POPULATION_GRIDS = {
  ghsl_census_scaled: 'GHSL 250 m przeskalowany do spisu 1 km',
  ghsl_raw: 'GHSL 250 m',
}

const nf = (v) => {
  const abs = Math.abs(v)
  const maximumFractionDigits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2
  return new Intl.NumberFormat('pl-PL', { maximumFractionDigits, useGrouping: 'always' }).format(v)
}

// Percentages arrive as 0-100 with unit "%": one decimal, Polish comma.
const pf = new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1, useGrouping: 'always' })

/** {text, missing}: "4 321 os./km²", "80,4 %" or "brak danych". */
export function formatValue(m) {
  if (m.value == null || Number.isNaN(m.value)) return { text: NO_DATA, missing: true }
  const unit = m.unit ? ` ${m.unit}` : ''
  const num = m.unit === '%' ? pf.format(m.value) : nf(m.value)
  return { text: `${num}${unit}`, missing: false }
}

/** Small print under a row: grid, feed variant, source, dates, coverage.
 *  When the row names its population grid, that readable name replaces the technical `grid` text. */
export function metricNotes(m) {
  const parts = []
  if (m.population_grid) parts.push(POPULATION_GRIDS[m.population_grid] || m.population_grid)
  else if (m.grid) parts.push(m.grid)
  if (m.feed_variant) parts.push(FEED_VARIANTS[m.feed_variant] || m.feed_variant)
  if (m.source) parts.push(m.source)
  if (m.population_date) parts.push(`ludność: ${m.population_date}`)
  if (m.timetable_date) parts.push(`rozkłady: ${m.timetable_date}`)
  if (m.coverage_share != null) parts.push(`pokrycie danymi: ${nf(m.coverage_share * 100)} %`)
  return parts.join(' · ')
}

/** Rows of one agglomeration grouped by domain: FUA, core, covered area, tram network, then any other.
 *  The file is already a curated subset in display order, so rows keep their file order within a domain;
 *  a row with tier "qa" never gets shown even if one slips in. */
export function groupMetrics(metrics, agglomeration) {
  const groups = new Map()
  for (const m of metrics || []) {
    if (m.agglomeration !== agglomeration) continue
    if (m.tier === 'qa') continue
    if (!groups.has(m.domain)) groups.set(m.domain, [])
    groups.get(m.domain).push(m)
  }
  const rank = (d) => (DOMAIN_ORDER.includes(d) ? DOMAIN_ORDER.indexOf(d) : DOMAIN_ORDER.length)
  return [...groups.entries()]
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
    .map(([domain, rows]) => ({ domain, title: DOMAIN_TITLES[domain] || domain, rows }))
}
