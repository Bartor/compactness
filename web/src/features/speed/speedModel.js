// Shared vocabulary of the scheduled-speed overlay: fixed speed classes, time bands and the compact property names
// of results/web/speed/*.geojson (pipeline/speed_web.py). Pure, no imports from the app.

/** Fixed, city-independent classes, km/h: below 12, 12-15, 15-18, 18-22, 22-26, 26 and above. */
export const CLASS_BREAKS = [12, 15, 18, 22, 26]
export const CLASS_LABELS = ['poniżej 12', '12–15', '15–18', '18–22', '22–26', '26 i więcej']
/** For a dark basemap: brighter = faster. */
export const CLASS_COLORS = ['#5B1A8C', '#952C80', '#C73E73', '#EF6A5A', '#FBA45C', '#FCE38A']
export const UNIT = 'km/h, z rozkładu'
export const SCHEDULED = 'rozkład, nie pomiar'

/** Band keys in the order of the class string `c` and of the line table arrays. */
export const BANDS = [
  { key: 'w_n', day: 'weekday', label: 'noc 23–05' },
  { key: 'w_e', day: 'weekday', label: 'wczesny ranek 05–07' },
  { key: 'w_am', day: 'weekday', label: 'szczyt poranny 07–09' },
  { key: 'w_md', day: 'weekday', label: 'międzyszczyt 09–15' },
  { key: 'w_pm', day: 'weekday', label: 'szczyt popołudniowy 15–18' },
  { key: 'w_ee', day: 'weekday', label: 'wczesny wieczór 18–20' },
  { key: 'w_ev', day: 'weekday', label: 'wieczór 20–23' },
  { key: 'w_all', day: 'weekday', label: 'cała doba' },
  { key: 's_n', day: 'saturday', label: 'noc 23–05' },
  { key: 's_mo', day: 'saturday', label: 'rano 05–09' },
  { key: 's_d', day: 'saturday', label: 'dzień 09–18' },
  { key: 's_ev', day: 'saturday', label: 'wieczór 18–23' },
  { key: 's_all', day: 'saturday', label: 'cała doba' },
]
export const DAYS = { weekday: 'środa', saturday: 'sobota' }
export const DEFAULT_BAND = 'w_am'
/** The bands shown as a small bar row in the popup (the all-day values are left out). */
export const POPUP_BANDS = BANDS.filter((b) => !b.key.endsWith('_all'))

export const bandIndex = (key) => BANDS.findIndex((b) => b.key === key)
export const bandOf = (key) => BANDS.find((b) => b.key === key) || BANDS[bandIndex(DEFAULT_BAND)]
export const bandText = (key) => { const b = bandOf(key); return `${DAYS[b.day]}, ${b.label}` }

/** Property names of one band. */
export const props = (key) => ({ v: `v_${key}`, t: `t_${key}`, a: `a_${key}`, al: `al_${key}`, ah: `ah_${key}`, fm: `fm_${key}` })

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

/** Class index 0..5 of a speed (a value on a break belongs to the upper class); -1 for no value. */
export function classOf(v) {
  if (!isNum(v)) return -1
  let i = 0
  for (const b of CLASS_BREAKS) if (v >= b) i++
  return i
}

/** The catalog ramp of the overlay ({stops, colors, labels}, one colour more than stops). */
export const RAMP = Object.freeze({ stops: CLASS_BREAKS, colors: CLASS_COLORS, labels: CLASS_LABELS })

/**
 * The +-1 minute rounding interval of a stretch speed: timetables are in whole minutes, so the stretch time may be
 * off by up to a minute. {lo, hi} km/h; hi is null when the time is a minute or less.
 */
export function roundingInterval(lengthM, speedKmh) {
  if (!isNum(lengthM) || !isNum(speedKmh) || speedKmh <= 0 || lengthM <= 0) return null
  const tMin = (lengthM / 1000) / speedKmh * 60
  const lo = (lengthM / 1000) / ((tMin + 1) / 60)
  const hi = tMin > 1 ? (lengthM / 1000) / ((tMin - 1) / 60) : null
  return { lo, hi, minutes: tMin }
}

/** ",3,5,7," -> ['3', '5', '7'] */
export const linesOf = (ln) => String(ln || '').split(',').map((s) => s.trim()).filter(Boolean)
/** "gdansk, gdynia" -> ['gdansk', 'gdynia'] */
export const feedsOf = (fd) => String(fd || '').split(',').map((s) => s.trim()).filter(Boolean)

/** Mode of a line row -> which overlay file draws it. */
export const MODE_GROUP = { tram: 'tram', bus: 'bus', trolleybus: 'bus', metro: 'rail', rail: 'rail' }
export const MODE_PL = { tram: 'tramwaj', bus: 'autobus', trolleybus: 'trolejbus', metro: 'metro', rail: 'kolej' }

/** Line-table row keys ("agg|feed|line") a map feature stands for. */
export function featureLineKeys(p) {
  if (!p) return []
  const feeds = feedsOf(p.fd)
  const out = []
  for (const f of feeds) for (const l of linesOf(p.ln)) out.push(`${p.agg}|${f}|${l}`)
  return out.sort()
}

/** True when a feature carries the line of row key "agg|feed|line". */
export function featureHasLine(p, key) {
  const [agg, feed, line] = String(key).split('|')
  return !!p && p.agg === agg && feedsOf(p.fd).includes(feed) && linesOf(p.ln).includes(line)
}
