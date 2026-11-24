import { useState } from 'react'
import ChartFrame, { CONTEXT_COLOR, DataTableSimple, LegendItem, SERIES_COLORS, useWidth } from './ChartFrame'
import { atLeastReadout, fmtMin, fmtPct } from './format'
import { keySet, linear, linePath, litKeys, nearestIndex, niceTicks, stepIndex } from './scales'

/** Class key of a value given the class limits (stops ascending): c0 below the first stop, cN at or above the last. */
export function classKeyOf(stops, x) {
  if (!stops?.length || x == null) return null
  let k = 0
  while (k < stops.length && x >= stops[k]) k++
  return `c${k}`
}

/** Which series get a colour: all when there are at most three, otherwise the highlighted / hot / pinned ones. */
export function colouredKeys(series, highlight, hotSeries, pinnedSeries) {
  if (series.length <= SERIES_COLORS.length && !highlight?.length) return series.map((s) => s.key)
  const want = [...(highlight || []), ...keySet(pinnedSeries), ...(hotSeries != null ? [hotSeries] : [])]
  return [...new Set(want)].filter((k) => series.some((s) => s.key === k)).slice(0, SERIES_COLORS.length)
}

/**
 * Inverted cumulative curve: the share of residents (y, %) with a value of at least x.
 *
 * Props
 *   series        [{key, label, xs, ys}] (data.atLeastSeries / headwaySeries); ys null = no data for that city
 *   highlight     keys to colour (at most 3; the selected city first). Others are grey context lines.
 *   unit          '%' (performance) or 'min' (headway: x = N minutes, y = share with service at least every N min)
 *   marks         class limits of the active map layer, ascending (e.g. [10, 20, 30, 40, 50, 60]); drawn as lines
 *   markColors    optional class colours (length = marks.length + 1), used for the lit class band
 *   floor         optional x of the access floor, drawn dashed and labelled "próg"
 *   hot, onHot, pinned, onPin                  class keys 'c0'..'cN' (the legend of the map layer)
 *   hotSeries, onHotSeries, pinnedSeries, onPinSeries   series keys (cities)
 *   colors        optional {key: colour}: fixed colours chosen by the app so a city keeps one colour in every chart;
 *                 when given, only these keys are coloured and `highlight` is ignored
 *   title, note, xLabel, height, what (read-out wording, e.g. 'kursy' for headway)
 */
export default function AtLeastCurve({
  series = [], highlight, unit = '%', marks, markColors, floor, hot = null, onHot, pinned, onPin,
  hotSeries = null, onHotSeries, pinnedSeries, onPinSeries, colors, title = 'Odsetek mieszkańców z co najmniej X',
  note, xLabel, height = 240, what = '',
}) {
  const [ref, width] = useWidth()
  const [cur, setCur] = useState(-1)
  const xs = series.find((s) => s.xs?.length)?.xs || []
  const m = { l: 44, r: 12, t: 10, b: 34 }
  const sx = linear([xs[0] ?? 0, xs[xs.length - 1] ?? 100], [m.l, Math.max(m.l + 10, width - m.r)])
  const sy = linear([0, 100], [height - m.b, m.t])
  const coloured = colors ? Object.keys(colors) : colouredKeys(series, highlight, hotSeries, pinnedSeries)
  const colorOf = (k) => (colors ? colors[k] || null : coloured.includes(k) ? SERIES_COLORS[coloured.indexOf(k)] : null)
  const litS = litKeys(hotSeries, pinnedSeries)
  const litC = litKeys(hot, pinned)
  const stops = marks || []
  const fx = unit === 'min' ? fmtMin : fmtPct
  const curX = cur >= 0 ? xs[cur] : null

  const setCursor = (i) => {
    setCur(i)
    if (onHot) onHot(i >= 0 && stops.length ? classKeyOf(stops, xs[i]) : null)
  }
  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - box.left) / box.width) * width
    setCursor(nearestIndex(xs, sx.invert(px)))
  }
  const onKey = (e) => {
    const n = stepIndex(e.key, cur, xs.length, { big: 5 })
    if (n != null) { e.preventDefault(); setCursor(n); return }
    if ((e.key === 'Enter' || e.key === ' ') && curX != null && onPin && stops.length) {
      e.preventDefault(); onPin(classKeyOf(stops, curX))
    }
    if (e.key === 'Escape') setCursor(-1)
  }
  const readFor = series.filter((s) => s.ys && (coloured.includes(s.key) || s.key === hotSeries))
  const readout = curX == null ? '' : readFor.map((s) =>
    `${s.label}: ${atLeastReadout(s.ys[cur], curX, { unit, what })}`).join('; ')

  // class bands lit from the legend (hot / pinned)
  const edges = [xs[0] ?? 0, ...stops, xs[xs.length - 1] ?? 100]
  const bands = stops.length ? edges.slice(0, -1).map((lo, k) => ({ key: `c${k}`, lo, hi: edges[k + 1] })) : []

  const legend = series.length > 1 ? (
    <>
      {series.filter((s) => colorOf(s.key)).map((s) => (
        <LegendItem key={s.key} color={colorOf(s.key)} label={s.label}
          lit={litS.size ? litS.has(s.key) : undefined}
          onEnter={() => onHotSeries?.(s.key)} onLeave={() => onHotSeries?.(null)} onClick={() => onPinSeries?.(s.key)} />
      ))}
      {series.some((s) => !colorOf(s.key)) ? <span className="chx-legend-note"><i className="chx-swatch-context" /> pozostałe miasta</span> : null}
    </>
  ) : null

  const tableXs = xs.filter((x) => (unit === 'min' ? true : x % 10 === 0))
  const table = (
    <DataTableSimple
      caption={title}
      head={[unit === 'min' ? 'Kursy co najmniej co' : 'Co najmniej', ...series.map((s) => s.label)]}
      rows={tableXs.map((x) => [fx(x), ...series.map((s) => fmtPct(s.ys?.[xs.indexOf(x)]))])}
    />
  )
  const yt = [0, 25, 50, 75, 100]
  const xt = unit === 'min' ? xs : niceTicks(xs[0] ?? 0, xs[xs.length - 1] ?? 100, Math.max(2, Math.floor(width / 70)))
  const ordered = [...series].sort((a, b) => (colorOf(a.key) ? 1 : 0) - (colorOf(b.key) ? 1 : 0))

  return (
    <ChartFrame title={title} note={note} readout={readout} table={table} legend={legend}>
      <div ref={ref} className="chx-plot">
        <svg
          width={width} height={height} role="img" tabIndex={0} className="chx-svg"
          aria-label={`${title}. Strzałki przesuwają kursor, Enter przypina klasę, Esc czyści.`}
          onMouseMove={onMove} onMouseLeave={() => setCursor(-1)} onKeyDown={onKey}
          onClick={() => { if (curX != null && onPin && stops.length) onPin(classKeyOf(stops, curX)) }}
        >
          {bands.filter((b) => litC.has(b.key)).map((b) => (
            <rect key={b.key} x={sx(b.lo)} y={m.t} width={Math.max(0, sx(b.hi) - sx(b.lo))} height={height - m.b - m.t}
              fill={markColors?.[Number(b.key.slice(1))] || 'var(--kit-focus, #7aa2e3)'} opacity=".16" />
          ))}
          {yt.map((v) => (
            <g key={v}>
              <line x1={m.l} x2={width - m.r} y1={sy(v)} y2={sy(v)} className="chx-grid" />
              <text x={m.l - 6} y={sy(v)} dy="0.32em" textAnchor="end" className="chx-tick">{fmtPct(v)}</text>
            </g>
          ))}
          {xt.map((v) => (
            <text key={v} x={sx(v)} y={height - m.b + 14} textAnchor="middle" className="chx-tick">{fx(v)}</text>
          ))}
          <text x={(m.l + width - m.r) / 2} y={height - 4} textAnchor="middle" className="chx-axis-label">
            {xLabel || (unit === 'min' ? 'kursy co najmniej co N min' : 'wynik co najmniej X (transport performance, %)')}
          </text>
          {stops.map((s) => (
            <line key={s} x1={sx(s)} x2={sx(s)} y1={m.t} y2={height - m.b} className="chx-mark" />
          ))}
          {floor != null ? (
            <g>
              <line x1={sx(floor)} x2={sx(floor)} y1={m.t} y2={height - m.b} className="chx-floor" />
              <text x={sx(floor) + 4} y={m.t + 10} className="chx-floor-label">próg {fx(floor)}</text>
            </g>
          ) : null}
          {ordered.map((s) => {
            const c = colorOf(s.key)
            const dim = litS.size > 0 && !litS.has(s.key)
            const d = linePath(s.xs || xs, s.ys, sx, sy, { step: unit === 'min' ? 'after' : null })
            return (
              <g key={s.key} opacity={dim ? 0.35 : 1}>
                <path d={d} fill="none" stroke={c || CONTEXT_COLOR} strokeWidth={c ? 2 : 1.25}
                  strokeLinejoin="round" />
                <path d={d} fill="none" stroke="transparent" strokeWidth="10" className="chx-hit"
                  onMouseEnter={() => onHotSeries?.(s.key)} onMouseLeave={() => onHotSeries?.(null)}
                  onClick={(e) => { if (onPinSeries) { e.stopPropagation(); onPinSeries(s.key) } }}>
                  <title>{s.label}</title>
                </path>
              </g>
            )
          })}
          {curX != null ? (
            <g pointerEvents="none">
              <line x1={sx(curX)} x2={sx(curX)} y1={m.t} y2={height - m.b} className="chx-cursor" />
              {readFor.map((s) => (s.ys[cur] == null ? null : (
                <circle key={s.key} cx={sx(curX)} cy={sy(s.ys[cur])} r="4" fill={colorOf(s.key) || CONTEXT_COLOR}
                  stroke="var(--kit-panel, #1c1f26)" strokeWidth="2" />
              )))}
            </g>
          ) : null}
        </svg>
      </div>
    </ChartFrame>
  )
}
