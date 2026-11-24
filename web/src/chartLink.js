// Linking of the distribution charts (features/charts) with the rest of the page: one colour per city across all
// charts, the city pins, the bridge from the map legend's class focus to the charts' class keys ("c0".."cN"), and
// the seven-city median of the time-of-day rows. Pure functions; no React.
import { SERIES_COLORS } from './features/charts'
import { focusOf } from './classFocus'

/** {cityId: colour}: the selected city takes the first colour, then pinned cities the next ones (three at most). */
export function cityColors(selected, pinned = []) {
  const order = [...new Set([selected, ...pinned].filter(Boolean))].slice(0, SERIES_COLORS.length)
  return Object.fromEntries(order.map((id, i) => [id, SERIES_COLORS[i]]))
}

/** The pins after a click on `id`: added, or removed when it was pinned. */
export const togglePin = (pinned, id) => (pinned.includes(id) ? pinned.filter((x) => x !== id) : [...pinned, id])

/** "c3" -> 3; anything else -> null. */
export const classIndexOf = (key) => (typeof key === 'string' && /^c\d+$/.test(key) ? Number(key.slice(1)) : null)

/**
 * The class focus of a layer as the charts' class props: {hot: 'c2' | null, pinned: ['c1', ...], onHot, onPin}.
 * `focus` is the page's useFocuses value, so the legend, the map and the charts show one state.
 */
export function classLink(focus, layerId) {
  const own = focusOf(focus.focuses, layerId)
  return {
    hot: own.hover != null ? `c${own.hover}` : null,
    pinned: (own.layerId === layerId ? own.pinned : []).map((i) => `c${i}`),
    onHot: (key) => focus.onHover(layerId, classIndexOf(key)),
    onPin: (key) => { const i = classIndexOf(key); if (i != null) focus.onToggle(layerId, i) },
  }
}

const median = (v) => {
  const a = v.filter((x) => typeof x === 'number' && Number.isFinite(x)).sort((p, q) => p - q)
  if (!a.length) return null
  const m = a.length >> 1
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2
}

/** Per window, the median over cities of v30 and v45: `lists` is [timeOfDayRows(...) per city]. */
export function medianRows(lists) {
  const first = lists.find((l) => l?.length)
  if (!first) return null
  return first.map((row, i) => ({
    key: row.key, label: row.label,
    v30: median(lists.map((l) => l?.[i]?.v30)), v45: median(lists.map((l) => l?.[i]?.v45)),
  }))
}
