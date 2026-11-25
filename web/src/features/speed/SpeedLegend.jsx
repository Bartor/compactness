import { CLASS_COLORS, CLASS_LABELS, SCHEDULED, bandText } from './speedModel'
import { WIDTHS, WIDTH_STOPS } from './lineLayers'

/** Width key rows of the overlay: [{width, label}] in px at zoom 13. */
export function widthKey() {
  return [null, ...WIDTH_STOPS].map((from, i) => {
    const to = i < WIDTH_STOPS.length ? WIDTH_STOPS[i] : null
    const label = from == null ? `poniżej ${to}` : to == null ? `${from} i więcej` : `${from}–${to}`
    return { width: WIDTHS[i], label }
  })
}

/** Class indices drawn at full strength: pinned plus the legend row under the pointer (as classFocus.emphasised). */
export function strongClasses(focus, layerId) {
  if (!focus || focus.layerId !== layerId) return new Set()
  const s = new Set(focus.pinned || [])
  if (focus.hover != null && focus.from === 'legend') s.add(focus.hover)
  return s
}

/**
 * The key of a "lines" overlay without its title: the six fixed speed classes (hover and pin like LegendBody:
 * onHover(layerId, index | null), onToggle(layerId, index), onClear(layerId)), the line widths (trips an hour),
 * dashes and offsets, and the band shown. `focus` is the layer's class focus ({layerId, hover, from, pinned}).
 */
export default function SpeedLegend({ layer, band, focus, onHover, onToggle, onClear }) {
  const strong = strongClasses(focus, layer.id)
  const pinned = focus?.layerId === layer.id ? focus.pinned || [] : []
  const under = focus?.layerId === layer.id ? focus.hover : null
  const rowClass = (i) => ['legend-row', pinned.includes(i) && 'pinned', under === i && 'hover',
    strong.size > 0 && !strong.has(i) && under !== i && 'dim'].filter(Boolean).join(' ')
  return (
    <>
      <em className="legend-unit">{`km/h, ${bandText(band)} (${SCHEDULED})`}</em>
      {CLASS_LABELS.map((label, i) => (
        <button
          key={label} type="button" aria-pressed={pinned.includes(i)} className={rowClass(i)}
          onMouseEnter={() => onHover?.(layer.id, i)} onMouseLeave={() => onHover?.(layer.id, null)}
          onFocus={() => onHover?.(layer.id, i)} onBlur={() => onHover?.(layer.id, null)}
          onClick={() => onToggle?.(layer.id, i)}
        >
          <i className="line-key" style={{ background: CLASS_COLORS[i] }} />{label}
        </button>
      ))}
      <div className="legend-sizes">
        <em className="legend-unit">grubość: kursy na godzinę w paśmie</em>
        <div className="legend-size-row">
          {widthKey().map((w) => (
            <span key={w.label}><i className="line-key" style={{ height: w.width, background: 'currentColor' }} />{w.label}</span>
          ))}
        </div>
      </div>
      <span><i className="line-key dashed" />{layer?.unit_kind === 'segments'
        ? 'linia przerywana: geometria w linii prostej między przystankami'
        : 'linia przerywana: odcinek krótszy niż 5 min, geometria w linii prostej albo feed nieoficjalny'}</span>
      <small className="legend-hint">
        Każdy kierunek jest narysowany po swojej prawej stronie. Odcinki bez kursów w paśmie nie są rysowane. Kliknij
        odcinek, by go zaznaczyć; kolejne kliknięcia dodają lub odejmują odcinki.
        {pinned.length > 0 && (
          <> <button type="button" className="legend-clear" onClick={() => onClear?.(layer.id)}>Pokaż wszystkie klasy</button></>
        )}
      </small>
    </>
  )
}
