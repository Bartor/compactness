import { useState } from 'react'
import { rampClasses, classLabel } from './ramp'
import { dataDates } from './layerInfo'

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
          {rampClasses(layer.ramp).map((c, i) => (
            <span key={i}><i className="sq" style={{ background: c.color }} />{classLabel(c)}</span>
          ))}
          <span><i className="sq hatch" />brak danych</span>
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
