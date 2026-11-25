// Words and numbers of the selection panel and the map tooltip, in Polish. Pure.
import { MODE_PL, bandText, props as bandProps, roundingInterval } from '../speed/speedModel'

export const NO_DATA = 'brak danych'
const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
const nfs = new Map()
/** Polish number: comma decimals, a non-breaking space between thousands. */
export function nf(v, d = 1) {
  const k = `${d}`
  if (!nfs.has(k)) nfs.set(k, new Intl.NumberFormat('pl-PL', { maximumFractionDigits: d, minimumFractionDigits: 0, useGrouping: 'always' }))
  return nfs.get(k).format(v)
}
export const num = (v, unit = '', d = 1) => (isNum(v) ? `${nf(v, d)}${unit ? ` ${unit}` : ''}` : NO_DATA)

/** Polish plural of a whole number: 1 kurs, 2-4 kursy (not 12-14), 5+ kursów. */
export function plural(n, one, few, many) {
  if (n === 1) return one
  const d = n % 10
  const t = n % 100
  return d >= 2 && d <= 4 && !(t >= 12 && t <= 14) ? few : many
}

/** "1:28" (minutes:seconds) for tables; "1:02:05" past an hour. */
export function mmss(s) {
  if (!isNum(s)) return NO_DATA
  const neg = s < 0
  let x = Math.round(Math.abs(s))
  const h = Math.floor(x / 3600); x -= h * 3600
  const m = Math.floor(x / 60); const sec = x - m * 60
  const ss = String(sec).padStart(2, '0')
  return (neg ? '−' : '') + (h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`)
}

/** "1 min 25 s", "12 min", "45 s" (rounded to whole seconds). */
export function duration(s) {
  if (!isNum(s)) return NO_DATA
  const neg = s < 0
  let x = Math.round(Math.abs(s))
  const h = Math.floor(x / 3600); x -= h * 3600
  const m = Math.floor(x / 60); const sec = x - m * 60
  const parts = []
  if (h) parts.push(`${h} h`)
  if (m || h) parts.push(`${m} min`)
  if (!h && (sec || !m)) parts.push(`${sec} s`)
  return (neg ? '−' : '') + parts.join(' ')
}

/** "17,2 km/h (±1 min: 15,8–18,9)" from a length and a speed, or a plain speed. */
export function speedText(v, iv, err = 1) {
  if (!isNum(v)) return NO_DATA
  if (!iv) return `${nf(v, 1)} km/h`
  const hi = iv.hi == null ? 'bez górnej granicy' : nf(iv.hi, 1)
  return `${nf(v, 1)} km/h (±${nf(err, 0)} min: ${nf(iv.lo, 1)}–${hi})`
}

/** "12–24 kursy na godzinę" / "12 kursów…" for a {min, max}. */
export function tphText(r) {
  if (!r) return NO_DATA
  const a = nf(r.min, 1)
  const b = nf(r.max, 1)
  return a === b ? a : `${a}–${b}`
}

/** The hover tooltip of a feature of a speed layer: {title, lines: [text]}. */
export function tipModel(p, band) {
  const k = bandProps(band)
  const v = p[k.v]
  const rail = p.m === 'rail' || p.m === 'metro'
  const out = []
  if (p[`z_${band}`]) out.push('0 min w rozkładzie: prędkości nie da się policzyć')
  else if (!isNum(v)) out.push('brak kursów w tym paśmie')
  else if (rail || !isNum(p.len)) out.push(`${nf(v, 1)} km/h z rozkładu`)
  else {
    const r = roundingInterval(p.len, v)
    const hi = r?.hi == null ? 'bez górnej granicy' : nf(r.hi, 1)
    out.push(`${nf(v, 1)} km/h z rozkładu (±1 min: ${r ? nf(r.lo, 1) : '?'}–${hi})`)
  }
  if (isNum(p[k.t])) out.push(`${nf(p[k.t], 1)} ${Number.isInteger(p[k.t]) ? plural(p[k.t], 'kurs', 'kursy', 'kursów') : 'kursu'} na godzinę`)
  const title = p.name || (p.line ? `Linia ${p.line}` : 'Odcinek')
  return { title, mode: MODE_PL[p.m] || '', lines: out }
}

export { bandText }
