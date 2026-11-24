// Polish number formatting for the charts: decimal comma, no-break space before units, "brak danych" for
// missing values (never 0). Pure functions, no React.

export const NO_DATA = 'brak danych'
const NBSP = ' '

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

/** A number with a decimal comma and `digits` decimals; thousands separated by a no-break space. */
export function fmtNum(v, digits = 0) {
  if (!isNum(v)) return NO_DATA
  const s = Math.abs(v).toFixed(digits)
  const [int, dec] = s.split('.')
  const grouped = int.length > 4 ? int.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP) : int
  const sign = v < 0 && Number(s) !== 0 ? '−' : ''
  return sign + grouped + (dec ? ',' + dec : '')
}

/** A percentage: "62 %" (no-break space). */
export function fmtPct(v, digits = 0) {
  return isNum(v) ? `${fmtNum(v, digits)}${NBSP}%` : NO_DATA
}

/** Minutes: "30 min". */
export function fmtMin(v) {
  return isNum(v) ? `${fmtNum(v, 0)}${NBSP}min` : NO_DATA
}

/** Points difference with an explicit sign: "+3,2 pkt". */
export function fmtPts(v, digits = 1) {
  if (!isNum(v)) return NO_DATA
  return `${v > 0 ? '+' : ''}${fmtNum(v, digits)}${NBSP}pkt`
}

/** Frequency format, easier to grasp than a percentage: "6 na 10". */
export function fmtOutOfTen(sharePct) {
  if (!isNum(sharePct)) return NO_DATA
  return `${Math.round(sharePct / 10)} na 10`
}

/**
 * The hover read-out of the "at least" curve:
 *   "62 % mieszkańców ma co najmniej 30 %"   (unit = '%', the default)
 *   "45 % mieszkańców ma kursy co najmniej co 10 min" (headway: unit = 'min', what = 'kursy')
 */
export function atLeastReadout(sharePct, x, { unit = '%', what = '', who = 'mieszkańców' } = {}) {
  if (!isNum(sharePct)) return `${NO_DATA} przy ${unit === 'min' ? fmtMin(x) : fmtPct(x)}`
  const xs = unit === 'min' ? fmtMin(x) : unit === '%' ? fmtPct(x) : `${fmtNum(x)}${NBSP}${unit}`
  return `${fmtPct(sharePct)} ${who} ma ${what ? what + ' ' : ''}co najmniej ${unit === 'min' ? 'co ' : ''}${xs}`
}
