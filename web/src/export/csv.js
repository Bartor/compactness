// CSV for spreadsheets, in the dialect of the kit's downloadCsv (which the KBR viewer uses with pl-PL): UTF-8 with a
// BOM so that Excel opens Polish letters correctly, semicolon between cells, decimal comma, CRLF between rows. The kit's
// toCsv writes numbers with the dot of JavaScript unless the caller formats them, and takes the dialect from the global
// locale; this builder takes it as an argument so that the output does not depend on a setting and can be tested.
// Numbers are written at the precision of the data (no rounding), a missing value is an empty cell, never 0.

export const BOM = '﻿'
export const DIALECT = { sep: ';', decimal: ',', eol: '\r\n' }

/** A number as a cell: all its digits, the decimal comma; empty for null, undefined, NaN or Infinity. */
export function csvNumber(v, decimal = DIALECT.decimal) {
  if (typeof v !== 'number' || !Number.isFinite(v)) return ''
  return String(v).replace('.', decimal)
}

/** One cell: numbers as above, text quoted when it holds the separator, a quote or a line break. */
export function csvCell(v, { sep, decimal } = DIALECT) {
  if (v == null) return ''
  if (typeof v === 'number') return csvNumber(v, decimal)
  if (typeof v === 'boolean') return v ? 'tak' : 'nie'
  const s = String(v)
  return s.includes(sep) || /["\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/** Rows of cells (header first) as CSV text with the BOM; the last row ends with a line break. */
export function buildCsv(rows, dialect = DIALECT) {
  const d = { ...DIALECT, ...dialect }
  return `${BOM}${rows.map((r) => r.map((c) => csvCell(c, d)).join(d.sep)).join(d.eol)}${d.eol}`
}
