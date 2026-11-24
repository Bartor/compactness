// Small pure helpers for SVG charts: linear scales, ticks, paths, nearest point, median, key sets.

/** Linear scale from [d0, d1] to [r0, r1]; .invert maps back. A zero-width domain maps to the middle. */
export function linear([d0, d1], [r0, r1]) {
  const span = d1 - d0
  const f = (v) => (span === 0 ? (r0 + r1) / 2 : r0 + ((v - d0) / span) * (r1 - r0))
  f.invert = (p) => (r1 === r0 ? d0 : d0 + ((p - r0) / (r1 - r0)) * span)
  f.domain = [d0, d1]
  f.range = [r0, r1]
  return f
}

/** "Nice" tick values between min and max, about `count` of them (steps 1, 2, 2.5, 5 x 10^k). */
export function niceTicks(min, max, count = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return []
  if (min === max) return [min]
  const raw = Math.abs(max - min) / Math.max(1, count)
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || 10 * mag
  const lo = Math.ceil(Math.min(min, max) / step - 1e-9) * step
  const out = []
  for (let v = lo; v <= Math.max(min, max) + step * 1e-9; v += step) out.push(Math.round(v / step) * step)
  return out.map((v) => Number(v.toPrecision(12)))
}

const ok = (v) => typeof v === 'number' && Number.isFinite(v)

/**
 * SVG path through (xs[i], ys[i]); a null / non-finite y breaks the line (missing data is a gap, never 0).
 * `step: 'after'` draws a staircase (value holds until the next x).
 */
export function linePath(xs, ys, sx, sy, { step = null } = {}) {
  let d = ''
  let pen = false
  for (let i = 0; i < xs.length; i++) {
    if (!ok(ys?.[i])) { pen = false; continue }
    const x = sx(xs[i]); const y = sy(ys[i])
    if (pen && step === 'after') d += `H${r(x)}V${r(y)}`
    else d += `${pen ? 'L' : 'M'}${r(x)},${r(y)}`
    pen = true
  }
  return d
}

/** Closed area between two series (a band), split where either bound is missing. */
export function bandPath(xs, lo, hi, sx, sy) {
  const parts = []
  let run = []
  const flush = () => {
    if (run.length > 1) {
      const top = run.map((i) => `${r(sx(xs[i]))},${r(sy(hi[i]))}`)
      const bot = run.slice().reverse().map((i) => `${r(sx(xs[i]))},${r(sy(lo[i]))}`)
      parts.push(`M${top.join('L')}L${bot.join('L')}Z`)
    }
    run = []
  }
  for (let i = 0; i < xs.length; i++) {
    if (ok(lo?.[i]) && ok(hi?.[i])) run.push(i)
    else flush()
  }
  flush()
  return parts.join('')
}

const r = (v) => Math.round(v * 10) / 10

/** Index of the x closest to `x` (xs sorted ascending). */
export function nearestIndex(xs, x) {
  if (!xs?.length) return -1
  let best = 0
  for (let i = 1; i < xs.length; i++) if (Math.abs(xs[i] - x) < Math.abs(xs[best] - x)) best = i
  return best
}

/** Median of the finite values (mean of the two middle ones for an even count); null when none. */
export function median(values) {
  const v = (values || []).filter(ok).sort((a, b) => a - b)
  if (!v.length) return null
  const m = Math.floor(v.length / 2)
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2
}

/** Min and max of the finite values across several arrays; [lo, hi] fallback when none. */
export function extent(arrays, fallback = [0, 1]) {
  let lo = Infinity; let hi = -Infinity
  for (const a of arrays) for (const v of a || []) if (ok(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v) }
  return lo === Infinity ? fallback : [lo, hi]
}

/** `pinned` may be a Set, an array, a single key or nothing; always returns a Set. */
export function keySet(pinned) {
  if (pinned instanceof Set) return pinned
  if (Array.isArray(pinned)) return new Set(pinned)
  return pinned == null ? new Set() : new Set([pinned])
}

/** Which keys are lit: the hot one plus the pinned ones. Empty = nothing lit (nothing dimmed). */
export function litKeys(hot, pinned) {
  const s = new Set(keySet(pinned))
  if (hot != null) s.add(hot)
  return s
}

/** The next index for an arrow key, clamped to [0, n - 1]; null for other keys. */
export function stepIndex(key, i, n, { big = 10 } = {}) {
  const at = i == null || i < 0 ? -1 : i
  const map = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: big, PageDown: -big }
  if (key === 'Home') return 0
  if (key === 'End') return n - 1
  if (!(key in map)) return null
  if (at < 0) return map[key] > 0 ? 0 : n - 1
  return Math.max(0, Math.min(n - 1, at + map[key]))
}

/** Domain widened to whole tick steps, with its ticks: niceDomain(0, 38) -> {domain: [0, 40], ticks: [0, 10, .., 40]}. */
export function niceDomain(min, max, count = 5) {
  let t = niceTicks(min, max, count)
  if (t.length < 2) return { domain: [min, max], ticks: t }
  const step = t[1] - t[0]
  if (t[0] > min + 1e-9) t = [Number((t[0] - step).toPrecision(12)), ...t]
  if (t[t.length - 1] < max - 1e-9) t = [...t, Number((t[t.length - 1] + step).toPrecision(12))]
  return { domain: [t[0], t[t.length - 1]], ticks: t }
}
