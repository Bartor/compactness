import { useState } from 'react'
import { dataDates, legendRows } from './layerInfo'
import { emphasised, hovered } from './classFocus'

const isPhone = () => typeof window !== 'undefined' && window.matchMedia('(max-width: 760px)').matches

/**
 * Colour key of the visible layers, with their data dates and sources. The classes of a value layer are
 * linked with the map: `focus` says which are hovered or pinned, `onHover(layerId, index | null)` and
 * `onToggle(layerId, index)` report the pointer and clicks, `onClear(layerId)` unpins everything.
 */
export default function Legend({ layers, focus, onHover, onToggle, onClear }) {
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
      {layers.map((l) => (
        <LegendBlock key={l.id} layer={l} focus={focus} onHover={onHover} onToggle={onToggle} onClear={onClear} />
      ))}
    </div>
  )
}

function LegendBlock({ layer, focus, onHover, onToggle, onClear }) {
  const dates = dataDates(layer)
  const { rows, noData } = legendRows(layer)
  const strong = focus ? emphasised(focus, layer.id) : new Set()
  const pinned = focus && focus.layerId === layer.id ? focus.pinned : []
  const under = focus ? hovered(focus, layer.id) : null
  const rowClass = (i) => ['legend-row', pinned.includes(i) && 'pinned', under === i && 'hover',
    strong.size > 0 && !strong.has(i) && under !== i && 'dim'].filter(Boolean).join(' ')
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
            <button
              key={i} type="button" aria-pressed={pinned.includes(i)}
              className={rowClass(i)}
              onMouseEnter={() => onHover?.(layer.id, i)} onMouseLeave={() => onHover?.(layer.id, null)}
              onFocus={() => onHover?.(layer.id, i)} onBlur={() => onHover?.(layer.id, null)}
              onClick={() => onToggle?.(layer.id, i)}
            >
              <i className="sq" style={{ background: r.color }} />{r.label}
            </button>
          ))}
          {noData && <span><i className="sq hatch" />{noData}</span>}
          <small className="legend-hint">
            {pinned.length
              ? <button type="button" className="legend-clear" onClick={() => onClear?.(layer.id)}>Pokaż wszystkie klasy</button>
              : 'Wskaż klasę, aby wyróżnić ją na mapie; kliknij, aby zostawić wyróżnienie.'}
          </small>
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
