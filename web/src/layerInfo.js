import { rampLegend } from './ramp'

/** "Ludność: 2020 · rozkłady: 2026-11-02", or '' when the layer has no dates. */
export function dataDates(layer) {
  const parts = []
  if (layer.population_date) parts.push(`ludność: ${layer.population_date}`)
  if (layer.timetable_date) parts.push(`rozkłady: ${layer.timetable_date}`)
  const s = parts.join(' · ')
  return s ? s[0].toUpperCase() + s.slice(1) : ''
}

/**
 * What the legend shows for a layer: colour rows and, when the layer can contain no-data cells
 * (catalog flag has_nodata), the label of the hatched row; null otherwise. A points layer also has
 * `noValue`: the label of nodes that are in the data but have no value for the coloured property.
 */
export function legendRows(layer) {
  if (!['choropleth', 'points'].includes(layer.kind) || !layer.ramp) return { rows: [], noData: null }
  const base = { rows: rampLegend(layer.ramp), noData: layer.has_nodata ? (layer.nodata_label || 'brak danych o rozkładach') : null }
  return layer.kind === 'points' ? { ...base, noValue: layer.novalue_label || null } : base
}
