// Pure helpers for the metrics table: grouping and formatting.
// A null value is "brak danych", never a zero.
export const NO_DATA = 'brak danych'

export const DOMAIN_TITLES = { fua: 'Cały obszar FUA', core: 'Rdzeń miasta' }
const DOMAIN_ORDER = ['fua', 'core']

const nf = (v) => {
  const abs = Math.abs(v)
  const maximumFractionDigits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2
  return new Intl.NumberFormat('pl-PL', { maximumFractionDigits, useGrouping: 'always' }).format(v)
}

/** {text, missing}: "4 321 os./km²" or "brak danych". */
export function formatValue(m) {
  if (m.value == null || Number.isNaN(m.value)) return { text: NO_DATA, missing: true }
  const unit = m.unit ? ` ${m.unit}` : ''
  return { text: `${nf(m.value)}${unit}`, missing: false }
}

/** Small print under a row: grid, source, dates, coverage. */
export function metricNotes(m) {
  const parts = []
  if (m.grid) parts.push(m.grid)
  if (m.source) parts.push(m.source)
  if (m.population_date) parts.push(`ludność: ${m.population_date}`)
  if (m.timetable_date) parts.push(`rozkłady: ${m.timetable_date}`)
  if (m.coverage_share != null) parts.push(`pokrycie danymi: ${nf(m.coverage_share * 100)} %`)
  return parts.join(' · ')
}

// tier: "main" may go on a graphic, "table" only in tables (shown, but secondary),
// "qa" is a control number and never shown in the map panel. Rows without a tier count as main.
const TIER_ORDER = ['main', 'table']
const tierRank = (m) => (m.tier && TIER_ORDER.includes(m.tier) ? TIER_ORDER.indexOf(m.tier) : 0)

/** True for rows that are shown, but as secondary (tier "table"). */
export const isSecondary = (m) => m.tier === 'table'

/** Rows of one agglomeration grouped by domain: FUA, core, then any other.
 *  QA-only rows are left out; within a domain "main" rows come before "table" rows. */
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
    .map(([domain, rows]) => ({
      domain,
      title: DOMAIN_TITLES[domain] || domain,
      rows: rows
        .map((m, i) => [m, i])
        .sort(([a, i], [b, j]) => tierRank(a) - tierRank(b) || i - j)
        .map(([m]) => m),
    }))
}
