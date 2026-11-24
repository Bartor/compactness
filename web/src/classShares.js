// Optional per-class shares of a city's residents (data/class_shares.json, {layerId: {agglomerationId: [share per
// class in ramp order]}}), shown in the legend when the file exists.

/** The shares of one layer for one agglomeration, or undefined. */
export function sharesFor(all, layerId, aggId) {
  const s = all?.[layerId]?.[aggId]
  return Array.isArray(s) && s.length ? s : undefined
}

/**
 * "23 %" for class `i`, "<1 %" for a tiny share, '' when there is no number. Shares are fractions of 1; a list
 * that adds up to more than 1.5 is taken to be in percent already.
 */
export function shareText(shares, i) {
  if (!Array.isArray(shares)) return ''
  const v = shares[i]
  if (typeof v !== 'number' || !Number.isFinite(v)) return ''
  const percent = shares.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0) > 1.5
  const p = percent ? v : v * 100
  if (p > 0 && p < 1) return '<1 %'
  return `${Math.round(p)} %`
}
