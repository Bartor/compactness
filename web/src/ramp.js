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

const nf = (v) => new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1, useGrouping: 'always' }).format(v)

/** "1 000-3 000 os./km²", "od 20 000", "poniżej 1 000" */
export function classLabel({ from, to }, unit = '') {
  const u = unit ? ` ${unit}` : ''
  if (from == null && to == null) return ''
  if (from == null) return `poniżej ${nf(to)}${u}`
  if (to == null) return `od ${nf(from)}${u}`
  return `${nf(from)}–${nf(to)}${u}`
}
