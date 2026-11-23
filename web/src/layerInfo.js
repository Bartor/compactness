/** "Ludność: 2020 · rozkłady: 2026-11-02", or '' when the layer has no dates. */
export function dataDates(layer) {
  const parts = []
  if (layer.population_date) parts.push(`ludność: ${layer.population_date}`)
  if (layer.timetable_date) parts.push(`rozkłady: ${layer.timetable_date}`)
  const s = parts.join(' · ')
  return s ? s[0].toUpperCase() + s.slice(1) : ''
}
