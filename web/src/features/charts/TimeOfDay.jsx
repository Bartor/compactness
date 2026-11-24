import { useState } from 'react'
import ChartFrame, { DataTableSimple, LegendItem, SERIES_COLORS, useWidth } from './ChartFrame'
import { fmtNum, fmtPct, NO_DATA } from './format'
import { timeTable } from './exportRows'
import { extent, linear, linePath, litKeys, niceDomain, stepIndex } from './scales'

/**
 * Four time windows (morning peak, midday, evening, Saturday) for one city: the 30 and 45 min values of one
 * measure as two lines with markers (circle = 30 min, square = 45 min).
 *
 * Props
 *   rows     [{key: 'pt_am'|..., label, v30, v45}] (data.timeOfDayRows)
 *   unit     '%' (default)
 *   compare  optional second set of rows (e.g. the seven-city median) drawn as thin grey lines, with compareLabel
 *   hot, onHot, pinned, onPin   window keys
 *   title, note, height
 */
export default function TimeOfDay({
  rows = [], unit = '%', compare = null, compareLabel = 'mediana siedmiu miast', hot = null, onHot, pinned, onPin,
  title = 'Pory dnia', note, height = 220, exportInfo,
}) {
  const [ref, width] = useWidth()
  const [cur, setCur] = useState(-1)
  const fmt = (v) => (unit === '%' ? fmtPct(v, 1) : v == null ? NO_DATA : fmtNum(v, 1))
  const m = { l: 44, r: 16, t: 12, b: 30 }
  const idx = rows.map((_, i) => i)
  const sx = linear([-0.5, rows.length - 0.5], [m.l, Math.max(m.l + 10, width - m.r)])
  let [lo, hi] = extent([rows.map((r) => r.v30), rows.map((r) => r.v45), compare?.map((r) => r.v30), compare?.map((r) => r.v45)], [0, 1])
  lo = Math.min(0, lo)
  const { domain, ticks } = niceDomain(lo, hi, 4)
  const sy = linear(domain, [height - m.b, m.t])
  const lit = litKeys(hot, pinned)
  const c30 = SERIES_COLORS[0]; const c45 = SERIES_COLORS[1]

  const setC = (i) => { setCur(i); onHot?.(i >= 0 ? rows[i]?.key ?? null : null) }
  const onKey = (e) => {
    const n = stepIndex(e.key, cur, rows.length, { big: 1 })
    if (n != null) { e.preventDefault(); setC(n) }
    if ((e.key === 'Enter' || e.key === ' ') && cur >= 0) { e.preventDefault(); onPin?.(rows[cur].key) }
    if (e.key === 'Escape') setC(-1)
  }
  const shown = cur >= 0 ? rows[cur] : rows.find((r) => r.key === hot)
  const readout = shown ? `${shown.label}: 30 min ${fmt(shown.v30)}, 45 min ${fmt(shown.v45)}` : ''
  const legend = (
    <>
      <LegendItem color={c30} shape="dot" label="30 min" />
      <LegendItem color={c45} shape="square" label="45 min" />
      {compare ? <LegendItem color="var(--kit-faint, #6b7385)" label={compareLabel} /> : null}
    </>
  )
  const table = (
    <DataTableSimple caption={title} head={['Pora', '30 min', '45 min', ...(compare ? [`${compareLabel}, 30`, `${compareLabel}, 45`] : [])]}
      rows={rows.map((r, i) => [r.label, fmt(r.v30), fmt(r.v45), ...(compare ? [fmt(compare[i]?.v30), fmt(compare[i]?.v45)] : [])])} />
  )
  const marker = (r, i, k, color, square) => (r[k] == null ? null : square
    ? <rect x={sx(i) - 4.5} y={sy(r[k]) - 4.5} width="9" height="9" fill={color} stroke="var(--kit-panel, #1c1f26)" strokeWidth="1.5" />
    : <circle cx={sx(i)} cy={sy(r[k])} r="5" fill={color} stroke="var(--kit-panel, #1c1f26)" strokeWidth="1.5" />)
  return (
    <ChartFrame
      title={title} note={note} readout={readout} table={table} legend={legend} exportInfo={exportInfo}
      exportData={() => timeTable(rows, compare, { unit, compareLabel })}
    >
      <div ref={ref} className="chx-plot">
        <svg width={width} height={height} role="img" tabIndex={0} className="chx-svg"
          aria-label={`${title}. Strzałki wybierają porę dnia, Enter przypina.`} onKeyDown={onKey} onMouseLeave={() => setC(-1)}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={m.l} x2={width - m.r} y1={sy(v)} y2={sy(v)} className="chx-grid" />
              <text x={m.l - 6} y={sy(v)} dy="0.32em" textAnchor="end" className="chx-tick">{unit === '%' ? fmtPct(v) : fmtNum(v)}</text>
            </g>
          ))}
          {rows.map((r, i) => {
            const on = lit.has(r.key) || i === cur
            return (
              <g key={r.key} className="chx-row" onMouseEnter={() => setC(i)} onClick={() => onPin?.(r.key)}>
                <rect x={sx(i - 0.5)} y={m.t} width={sx(i + 0.5) - sx(i - 0.5)} height={height - m.b - m.t} className={on ? 'chx-rowbg on' : 'chx-rowbg'} />
                <text x={sx(i)} y={height - m.b + 16} textAnchor="middle" className={on ? 'chx-label sel' : 'chx-label'}>{r.label}</text>
              </g>
            )
          })}
          {compare ? (
            <g pointerEvents="none">
              <path d={linePath(idx, compare.map((r) => r.v30), sx, sy)} fill="none" stroke="var(--kit-faint, #6b7385)" strokeWidth="1.25" />
              <path d={linePath(idx, compare.map((r) => r.v45), sx, sy)} fill="none" stroke="var(--kit-faint, #6b7385)" strokeWidth="1.25" strokeDasharray="4 3" />
            </g>
          ) : null}
          <g pointerEvents="none">
            <path d={linePath(idx, rows.map((r) => r.v30), sx, sy)} fill="none" stroke={c30} strokeWidth="2" />
            <path d={linePath(idx, rows.map((r) => r.v45), sx, sy)} fill="none" stroke={c45} strokeWidth="2" />
            {rows.map((r, i) => <g key={r.key}>{marker(r, i, 'v30', c30, false)}{marker(r, i, 'v45', c45, true)}</g>)}
          </g>
        </svg>
      </div>
    </ChartFrame>
  )
}
