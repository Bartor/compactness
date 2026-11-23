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
 * (catalog flag has_nodata), the label of the hatched row; null otherwise.
 */
export function legendRows(layer) {
  if (layer.kind !== 'choropleth' || !layer.ramp) return { rows: [], noData: null }
  return { rows: rampLegend(layer.ramp), noData: layer.has_nodata ? (layer.nodata_label || 'brak danych GTFS') : null }
}
