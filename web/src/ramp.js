// Colour ramps from the catalog -> MapLibre expressions and legend rows.
// A ramp is {stops: [...], colors: [...]}; value v belongs to the class whose
// lower bound is the largest stop <= v (below the first stop: the first
// colour). With one colour more than stops, the first colour is for values
// below the first stop and stops[i] starts colour i + 1.

/** Bounds and colours of the classes, in order; null = open end. */
export function rampClasses(ramp) {
  const { stops, colors } = ramp
  if (colors.length === stops.length + 1) {
    return colors.map((color, i) => ({
      color,
      from: i === 0 ? null : stops[i - 1],
      to: i < stops.length ? stops[i] : null,
    }))
  }
  return colors.map((color, i) => ({
    color,
    from: i === 0 ? null : stops[i],
    to: i + 1 < stops.length ? stops[i + 1] : null,
  }))
}

/** True when the feature property is a real number (null, missing, text = no data). */
export const hasValue = (property) => ['==', ['typeof', ['get', property]], 'number']

/** fill-color: a step over the property; no data is transparent here, a separate hatched layer draws it. */
export function rampExpression(property, ramp, noData = 'rgba(0,0,0,0)') {
  const classes = rampClasses(ramp)
  const step = ['step', ['get', property], classes[0].color]
  for (let i = 1; i < classes.length; i++) step.push(classes[i].from, classes[i].color)
  return ['case', hasValue(property), step, noData]
}

/** Index of the ramp class a value falls into (the order of rampClasses and of the legend rows). */
export function classIndex(ramp, v) {
  const classes = rampClasses(ramp)
  let i = 0
  for (let k = 1; k < classes.length; k++) if (v >= classes[k].from) i = k
  return i
}

/**
 * fill-opacity with some classes emphasised: those keep `base`, the others drop to `dim`.
 * `emphasised` is a Set of class indices; empty means no emphasis, so every class gets `base`.
 */
export function focusOpacity(property, ramp, emphasised, base = 0.8, dim = 0.1) {
  if (!emphasised || emphasised.size === 0) return base
  const classes = rampClasses(ramp)
  const op = (i) => (emphasised.has(i) ? base : dim)
  const step = ['step', ['get', property], op(0)]
  for (let i = 1; i < classes.length; i++) step.push(classes[i].from, op(i))
  return step
}

const nf = (v) => new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1, useGrouping: 'always' }).format(v)

/** "1 000-3 000 os./km²", "od 20 000", "poniżej 1 000" */
export function classLabel({ from, to }, unit = '') {
  const u = unit ? ` ${unit}` : ''
  if (from == null && to == null) return ''
  if (from == null) return `poniżej ${nf(to)}${u}`
  if (to == null) return `od ${nf(from)}${u}`
  return `${nf(from)}–${nf(to)}${u}`
}

/**
 * Legend rows of a ramp: [{color, label}] in ramp order. A ramp may carry its own `labels`
 * (one per colour, for classes that are not numeric ranges); otherwise they come from the bounds.
 */
export function rampLegend(ramp, unit = '') {
  const classes = rampClasses(ramp)
  const own = Array.isArray(ramp.labels) && ramp.labels.length === classes.length ? ramp.labels : null
  return classes.map((c, i) => ({ color: c.color, label: own ? own[i] : classLabel(c, unit) }))
}
