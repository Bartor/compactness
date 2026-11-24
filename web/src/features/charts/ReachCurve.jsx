import { useState } from 'react'
import ChartFrame, { CONTEXT_COLOR, DataTableSimple, LegendItem, SERIES_COLORS, useWidth } from './ChartFrame'
import { colouredKeys } from './AtLeastCurve'
import { fmtMin, fmtPct } from './format'
import { reachTable } from './exportRows'
import { bandPath, extent, linear, linePath, litKeys, nearestIndex, niceTicks, stepIndex } from './scales'

/** Thresholds below this are dominated by the resident's own cell (see the QA note); shaded and labelled. */
export const SHORT_MIN = 15

/**
 * Reach by time threshold, 5-60 min: the ratio of means (line) and, for the focus city, the band between the
 * 25th and 75th percentile of residents with the median dotted.
 *
 * Props
 *   series     [{key, label, xs, rom, p25, p50, p75}] (data.reachSeries)
 *   focus      key of the city whose band is drawn (default: hot, else first pinned, else the first series)
 *   highlight  keys to colour (at most 3); others grey
 *   colors     optional {key: colour} fixed by the app (as in AtLeastCurve)
 *   hot, onHot, pinned, onPin   city keys
 *   title, note, height
 */
export default function ReachCurve({
  series = [], focus, highlight, colors, hot = null, onHot, pinned, onPin, title = 'Zasięg w zależności od czasu podróży',
  note, height = 240, exportInfo,
}) {
  const [ref, width] = useWidth()
  const [cur, setCur] = useState(-1)
  const xs = series.find((s) => s.xs?.length)?.xs || []
  const m = { l: 44, r: 12, t: 10, b: 34 }
  const sx = linear([xs[0] ?? 0, xs[xs.length - 1] ?? 60], [m.l, Math.max(m.l + 10, width - m.r)])
  const [, hiY] = extent(series.flatMap((s) => [s.rom, s.p75]), [0, 100])
  const yMax = Math.max(10, Math.ceil(hiY / 10) * 10)
  const sy = linear([0, yMax], [height - m.b, m.t])
  const coloured = colors ? Object.keys(colors) : colouredKeys(series, highlight, hot, pinned)
  const colorOf = (k) => (colors ? colors[k] || null : coloured.includes(k) ? SERIES_COLORS[coloured.indexOf(k)] : null)
  const lit = litKeys(hot, pinned)
  const fkey = focus ?? hot ?? [...lit][0] ?? coloured[0] ?? series[0]?.key
  const f = series.find((s) => s.key === fkey)
  const fc = colorOf(fkey) || SERIES_COLORS[0]

  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect()
    setCur(nearestIndex(xs, sx.invert(((e.clientX - box.left) / box.width) * width)))
  }
  const onKey = (e) => {
    const n = stepIndex(e.key, cur, xs.length, { big: 3 })
    if (n != null) { e.preventDefault(); setCur(n) }
    if ((e.key === 'Enter' || e.key === ' ') && fkey != null && onPin) { e.preventDefault(); onPin(fkey) }
    if (e.key === 'Escape') setCur(-1)
  }
  const readout = cur < 0 || !f ? '' : `${f.label}, ${fmtMin(xs[cur])}: zasięg ${fmtPct(f.rom?.[cur], 1)} (stosunek średnich); `
    + `połowa mieszkańców ma co najmniej ${fmtPct(f.p50?.[cur], 1)}, środkowa połowa od ${fmtPct(f.p25?.[cur], 1)} do ${fmtPct(f.p75?.[cur], 1)}`

  const legend = (
    <>
      {series.filter((s) => colorOf(s.key)).map((s) => (
        <LegendItem key={s.key} color={colorOf(s.key)} label={s.label} lit={lit.size ? lit.has(s.key) : undefined}
          onEnter={() => onHot?.(s.key)} onLeave={() => onHot?.(null)} onClick={() => onPin?.(s.key)} />
      ))}
      {f ? <LegendItem color={fc} shape="band" label={`${f.label}: 25.–75. percentyl mieszkańców`} /> : null}
      {f ? <LegendItem color={fc} dashed label="mediana" /> : null}
    </>
  )
  const table = (
    <DataTableSimple
      caption={title}
      head={['Czas', ...series.flatMap((s) => (s.key === fkey ? [`${s.label}: stosunek średnich`, '25. perc.', 'mediana', '75. perc.'] : [s.label]))]}
      rows={xs.map((x, i) => [fmtMin(x), ...series.flatMap((s) => (s.key === fkey
        ? [fmtPct(s.rom?.[i], 1), fmtPct(s.p25?.[i], 1), fmtPct(s.p50?.[i], 1), fmtPct(s.p75?.[i], 1)]
        : [fmtPct(s.rom?.[i], 1)]))])}
    />
  )
  const ordered = [...series].sort((a, b) => (colorOf(a.key) ? 1 : 0) - (colorOf(b.key) ? 1 : 0))
  return (
    <ChartFrame
      title={title} note={note} readout={readout} table={table} legend={legend} exportInfo={exportInfo}
      exportData={() => reachTable(series)}
    >
      <div ref={ref} className="chx-plot">
        <svg width={width} height={height} role="img" tabIndex={0} className="chx-svg"
          aria-label={`${title}. Strzałki zmieniają próg czasu, Enter przypina miasto, Esc czyści.`}
          onMouseMove={onMove} onMouseLeave={() => setCur(-1)} onKeyDown={onKey}>
          {xs.length && xs[0] < SHORT_MIN ? (
            <g>
              <rect x={sx(xs[0])} y={m.t} width={sx(SHORT_MIN) - sx(xs[0])} height={height - m.b - m.t} className="chx-shade" />
              <text x={sx(xs[0]) + 3} y={m.t + 10} className="chx-tick">własna komórka</text>
            </g>
          ) : null}
          {niceTicks(0, yMax, 4).map((v) => (
            <g key={v}>
              <line x1={m.l} x2={width - m.r} y1={sy(v)} y2={sy(v)} className="chx-grid" />
              <text x={m.l - 6} y={sy(v)} dy="0.32em" textAnchor="end" className="chx-tick">{fmtPct(v)}</text>
            </g>
          ))}
          {xs.filter((x) => x % 15 === 0 || x === xs[0]).map((x) => (
            <text key={x} x={sx(x)} y={height - m.b + 14} textAnchor="middle" className="chx-tick">{fmtMin(x)}</text>
          ))}
          <text x={(m.l + width - m.r) / 2} y={height - 4} textAnchor="middle" className="chx-axis-label">próg czasu podróży</text>
          {f ? (
            <g pointerEvents="none">
              <path d={bandPath(xs, f.p25, f.p75, sx, sy)} fill={fc} opacity=".2" />
              <path d={linePath(xs, f.p50, sx, sy)} fill="none" stroke={fc} strokeWidth="1.5" strokeDasharray="4 3" />
            </g>
          ) : null}
          {ordered.map((s) => {
            const c = colorOf(s.key)
            const d = linePath(xs, s.rom, sx, sy)
            return (
              <g key={s.key} opacity={lit.size && !lit.has(s.key) ? 0.35 : 1}>
                <path d={d} fill="none" stroke={c || CONTEXT_COLOR} strokeWidth={c ? 2 : 1.25} strokeLinejoin="round" />
                <path d={d} fill="none" stroke="transparent" strokeWidth="10" className="chx-hit"
                  onMouseEnter={() => onHot?.(s.key)} onMouseLeave={() => onHot?.(null)} onClick={() => onPin?.(s.key)}>
                  <title>{s.label}</title>
                </path>
              </g>
            )
          })}
          {cur >= 0 && f ? (
            <g pointerEvents="none">
              <line x1={sx(xs[cur])} x2={sx(xs[cur])} y1={m.t} y2={height - m.b} className="chx-cursor" />
              {f.rom?.[cur] != null ? <circle cx={sx(xs[cur])} cy={sy(f.rom[cur])} r="4" fill={fc} stroke="var(--kit-panel, #1c1f26)" strokeWidth="2" /> : null}
            </g>
          ) : null}
        </svg>
      </div>
    </ChartFrame>
  )
}
