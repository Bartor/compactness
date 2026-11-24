import { useState } from 'react'
import { dataDates, legendRows } from './layerInfo'
import { emphasised, focusOf, hovered } from './classFocus'
import { sizeClasses } from './pointLayers'
import { usePhone } from './usePhone'

/**
 * Phone only: a collapsed "Legenda" button over the map that opens the key of the visible layers, with their
 * data dates and sources. On desktop the key is in the sidebar, under each layer (LegendBody), and this
 * renders nothing. `focuses` ({layerId: focus}) says which classes are hovered or pinned, `onHover(layerId,
 * index | null)` and `onToggle(layerId, index)` report the pointer and clicks, `onClear(layerId)` unpins all.
 */
export default function Legend({ layers, focuses, onHover, onToggle, onClear }) {
  const phone = usePhone()
  const [open, setOpen] = useState(false)
  if (!phone || !layers.length) return null
  if (!open) {
    return (
      <button type="button" className="kit-map-legend closed" onClick={() => setOpen(true)}>Legenda</button>
    )
  }
  return (
    <div className="kit-map-legend legend">
      <button type="button" className="kit-legend-close" aria-label="Zwiń legendę" onClick={() => setOpen(false)}>×</button>
      {layers.map((l) => {
        const dates = dataDates(l)
        return (
          <div key={l.id} className="legend-block">
            <b>{l.title}</b>
            <LegendBody layer={l} focus={focusOf(focuses || {}, l.id)} onHover={onHover} onToggle={onToggle} onClear={onClear} />
            {dates && <small>{dates}</small>}
            {l.attribution && <small>{l.attribution}</small>}
          </div>
        )
      })}
    </div>
  )
}

/** The key of one layer without its title, dates and sources: shared by the sidebar and the phone overlay. */
export function LegendBody({ layer, focus, onHover, onToggle, onClear }) {
  const { rows, noData, noValue } = legendRows(layer)
  const points = layer.kind === 'points'
  const strong = emphasised(focus, layer.id)
  const pinned = focus.layerId === layer.id ? focus.pinned : []
  const under = hovered(focus, layer.id)
  const rowClass = (i) => ['legend-row', pinned.includes(i) && 'pinned', under === i && 'hover',
    strong.size > 0 && !strong.has(i) && under !== i && 'dim'].filter(Boolean).join(' ')
  return (
    <>
      {layer.kind === 'boundary' && (
        <>
          <span><i className="line" style={{ background: '#1D4ED8' }} />obszar funkcjonalny (FUA)</span>
          <span><i className="line dashed" />rdzeń miasta</span>
        </>
      )}
      {(layer.kind === 'choropleth' || points) && layer.ramp && (
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
              <i className={points ? 'dot' : 'sq'} style={{ background: r.color }} />{r.label}
            </button>
          ))}
          {points && layer.size_stops && (
            <div className="legend-sizes">
              <em className="legend-unit">{layer.size_label}</em>
              <div className="legend-size-row">
                {sizeClasses(layer).map((c) => (
                  <span key={c.label}>
                    <i className="dot size" style={{ width: 2 * c.radius, height: 2 * c.radius }} />{c.label}
                  </span>
                ))}
              </div>
            </div>
          )}
          {noData && <span><i className={points ? 'dot ring' : 'sq hatch'} />{noData}</span>}
          {noValue && <span><i className="dot ring" />{noValue}</span>}
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
    </>
  )
}
