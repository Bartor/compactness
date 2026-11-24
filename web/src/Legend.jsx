import { legendRows } from './layerInfo'
import { emphasised, focusOf, hovered } from './classFocus'
import { sizeClasses } from './pointLayers'
import { shareFractions, shareText } from './classShares'
import { KIND_ORDER } from './mapLayers'
import { ScopeLine } from './ClassChart'
import MapLegendBox from './kitx/MapLegendBox'

/**
 * The legend in the corner of the map (desktop and phone): the active value layer with its classes (hover and pin as
 * in the sidebar before: they drive the map and the charts) and the unit, then a compact key of each active overlay.
 * No dates and no sources here; they are behind the "?" of the layer in the sidebar. `open` / `onToggle` is the fold
 * state, kept by the page. `shares` is {scopeOf(layerId) -> scope | null (classShares.scopeData), aggName, area,
 * onArea}: with it every class of a value layer shows the share of residents of the scope, and a line says whose
 * numbers those are.
 */
export default function Legend({ layers, focuses, onHover, onToggle, onClear, open, onOpen, shares }) {
  if (!layers.length) return null
  const ordered = [...layers].sort((a, b) => (KIND_ORDER[a.kind] ?? 9) - (KIND_ORDER[b.kind] ?? 9))
  return (
    <MapLegendBox open={open} onToggle={onOpen}>
      {ordered.map((l) => {
        const scope = l.kind === 'choropleth' ? shares?.scopeOf(l.id) : null
        const fr = shareFractions(scope)
        return (
          <div key={l.id} className="legend-block">
            <b>{l.title}</b>
            <LegendBody
              layer={l} focus={focusOf(focuses || {}, l.id)} onHover={onHover} onToggle={onToggle} onClear={onClear}
              shares={fr?.pop} noDataShare={fr?.nodataPop} compact
            />
            {scope && <ScopeLine aggName={shares.aggName} area={shares.area} onArea={shares.onArea} />}
          </div>
        )
      })}
    </MapLegendBox>
  )
}

/**
 * The key of one layer without its title, dates and sources. `shares` (optional) is, per class in ramp order, the
 * share of residents as a fraction (classShares.shareFractions().pop), `noDataShare` the same for the hatched row;
 * `compact` drops the explanatory line under the classes (it stays as "Pokaż wszystkie klasy" while a class is pinned).
 */
export function LegendBody({ layer, focus, onHover, onToggle, onClear, shares, noDataShare = null, compact = false }) {
  const { rows, noData, noValue } = legendRows(layer)
  const points = layer.kind === 'points'
  const strong = emphasised(focus, layer.id)
  const pinned = focus.layerId === layer.id ? focus.pinned : []
  const under = hovered(focus, layer.id)
  const rowClass = (i) => ['legend-row', pinned.includes(i) && 'pinned', under === i && 'hover',
    strong.size > 0 && !strong.has(i) && under !== i && 'dim'].filter(Boolean).join(' ')
  const noDataText = noDataShare == null ? '' : shareText([noDataShare], 0)
  return (
    <>
      {layer.kind === 'boundary' && (
        <>
          <span><i className="line" />obszar funkcjonalny (FUA)</span>
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
              {shareText(shares, i) && <em className="legend-share">{shareText(shares, i)}</em>}
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
          {noData && (
            <span>
              <i className={points ? 'dot ring' : 'sq hatch'} />{noData}
              {noDataText && <em className="legend-share">{noDataText}</em>}
            </span>
          )}
          {noValue && <span><i className="dot ring" />{noValue}</span>}
          {(pinned.length > 0 || !compact) && (
            <small className="legend-hint">
              {pinned.length
                ? <button type="button" className="legend-clear" onClick={() => onClear?.(layer.id)}>Pokaż wszystkie klasy</button>
                : 'Wskaż klasę, aby wyróżnić ją na mapie; kliknij, aby zostawić wyróżnienie.'}
            </small>
          )}
        </>
      )}
      {layer.kind === 'mask' && (
        <span><i className="sq hatch" />{layer.legend || layer.caption || 'brak danych'}</span>
      )}
    </>
  )
}
