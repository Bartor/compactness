import { useEffect, useRef, useState } from 'react'
import { legendRows } from './layerInfo'
import { emphasised, focusOf, hovered } from './classFocus'
import { sizeClasses } from './pointLayers'
import { shareFractions, shareText } from './classShares'
import { KIND_ORDER } from './mapLayers'
import { ScopeLine } from './ClassChart'
import MapLegendBox from './kitx/MapLegendBox'
import SpeedLegend from './features/speed/SpeedLegend'

/**
 * The legend in the corner of the map (desktop and phone): the active value layer with its classes (hover and pin drive
 * the map and the charts) and the unit, then a compact key of each active overlay, collapsed until asked for. No dates and
 * no sources here; they are behind the "?" of the layer in the sidebar. `open` / `onOpen` is the fold state, kept by the
 * page. `shares` is {scopeOf(layerId) -> scope | null (classShares.scopeData), aggName, area, noDataFor(layerId)}: with it
 * every class of a value layer shows the share of residents of the scope, and a line says whose numbers those are, in the
 * area chosen in the header. `noDataFor(layerId)` says that the selected city has nothing for the layer; `loading` that
 * the tiles of the value layer are still coming. `extra` is one more section above the layers (the isochrone card).
 */
export default function Legend({ layers, focuses, onHover, onToggle, onClear, open, onOpen, shares, loading = false, extra = null }) {
  const scroll = useRef(null)
  const key = layers.map((l) => l.id).sort().join('|')
  useEffect(() => { if (scroll.current) scroll.current.scrollTop = 0 }, [key, open])
  if (!layers.length && !extra) return null
  // the speed layers (tram, bus, rail) share one key and one class focus: the first of them stands for all
  const lead = layers.find((l) => l.kind === 'lines')
  const ordered = layers.filter((l) => l.kind !== 'lines' || l === lead)
    .map((l) => (l === lead ? { ...l, title: 'Prędkość z rozkładu' } : l))
    .sort((a, b) => (KIND_ORDER[a.kind] ?? 9) - (KIND_ORDER[b.kind] ?? 9))
  return (
    <MapLegendBox open={open} onToggle={onOpen} scrollRef={scroll}>
      {extra && <div className="legend-block legend-extra">{extra}</div>}
      {ordered.map((l) => (
        <LegendSection
          key={l.id} layer={l} focuses={focuses} onHover={onHover} onToggle={onToggle} onClear={onClear} shares={shares}
          loading={loading && l.kind === 'choropleth'} startOpen={l.kind === 'choropleth' || l.kind === 'boundary' || l.kind === 'lines'}
        />
      ))}
    </MapLegendBox>
  )
}

function LegendSection({ layer: l, focuses, onHover, onToggle, onClear, shares, loading, startOpen }) {
  const [open, setOpen] = useState(startOpen)
  const scope = l.kind === 'choropleth' ? shares?.scopeOf(l.id) : null
  const fr = shareFractions(scope)
  const none = l.kind === 'choropleth' && shares?.noDataFor?.(l.id)
  return (
    <div className="legend-block">
      {startOpen
        ? <b>{l.title}</b>
        : (
          <button type="button" className="legend-fold" aria-expanded={open} onClick={() => setOpen(!open)}>
            <span aria-hidden="true">{open ? '▾' : '▸'}</span> {l.title}
          </button>
        )}
      {loading && <small className="legend-loading" role="status">Wczytywanie warstwy…</small>}
      {none && <p className="legend-none">Brak danych o rozkładach dla: {shares.aggName}</p>}
      {open && !none && (
        <>
          <LegendBody
            layer={l} focus={focusOf(focuses || {}, l.id)} onHover={onHover} onToggle={onToggle} onClear={onClear}
            shares={fr?.pop} noDataShare={fr?.nodataPop} compact
          />
          {scope && <ScopeLine aggName={shares.aggName} area={shares.area} />}
        </>
      )}
    </div>
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
      {layer.kind === 'lines' && (
        <SpeedLegend layer={layer} band={layer.band} focus={focus} onHover={onHover} onToggle={onToggle} onClear={onClear} />
      )}
      {layer.kind === 'boundary' && (
        <>
          <span><i className="line" />obszar aglomeracji</span>
          <span><i className="line dashed" />samo miasto</span>
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
        <span><i className="sq hatch" />{layer.legend || layer.caption || 'brak danych o rozkładach'}</span>
      )}
    </>
  )
}
