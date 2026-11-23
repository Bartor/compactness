import { useState } from 'react'
import { dataDates, legendRows } from './layerInfo'

const isPhone = () => typeof window !== 'undefined' && window.matchMedia('(max-width: 760px)').matches

/** Colour key of the visible layers, with their data dates and sources. */
export default function Legend({ layers }) {
  const [open, setOpen] = useState(() => !isPhone())
  if (!layers.length) return null
  if (!open) {
    return (
      <button type="button" className="kit-map-legend closed" onClick={() => setOpen(true)}>Legenda</button>
    )
  }
  return (
    <div className="kit-map-legend legend">
      <button type="button" className="kit-legend-close" aria-label="Zwiń legendę" onClick={() => setOpen(false)}>×</button>
      {layers.map((l) => <LegendBlock key={l.id} layer={l} />)}
    </div>
  )
}

function LegendBlock({ layer }) {
  const dates = dataDates(layer)
  const { rows, noData } = legendRows(layer)
  return (
    <div className="legend-block">
      <b>{layer.title}</b>
      {layer.kind === 'boundary' && (
        <>
          <span><i className="line" style={{ background: '#1D4ED8' }} />obszar funkcjonalny (FUA)</span>
          <span><i className="line dashed" />rdzeń miasta</span>
        </>
      )}
      {layer.kind === 'choropleth' && layer.ramp && (
        <>
          {layer.unit && <em className="legend-unit">{layer.unit}</em>}
          {rows.map((r, i) => (
            <span key={i}><i className="sq" style={{ background: r.color }} />{r.label}</span>
          ))}
          {noData && <span><i className="sq hatch" />{noData}</span>}
        </>
      )}
      {layer.kind === 'mask' && (
        <span><i className="sq hatch" />{layer.legend || layer.caption || 'brak danych'}</span>
      )}
      {dates && <small>{dates}</small>}
      {layer.attribution && <small>{layer.attribution}</small>}
    </div>
  )
}
