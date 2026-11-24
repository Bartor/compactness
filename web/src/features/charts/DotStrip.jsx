import { useState } from 'react'
import ChartFrame, { DataTableSimple, SERIES_COLORS, useWidth } from './ChartFrame'
import { fmtNum, fmtPct, NO_DATA } from './format'
import { extent, linear, litKeys, niceDomain, stepIndex } from './scales'

const fmtBy = (unit) => (v) => (unit === '%' ? fmtPct(v, 1) : v == null ? NO_DATA : `${fmtNum(v, unit ? 1 : 2)}${unit ? ' ' + unit : ''}`)

/**
 * Seven cities on one axis for one measure: a ranked dot plot (one row per city, shared x axis), the selected city
 * in the accent colour, the seven-city median as a vertical line. Cities without data are listed as "brak danych".
 *
 * Props
 *   rows      [{key, label, value}]; median (number); label (measure name); unit ('%', '', or a text unit)
 *   better    'high' | 'low' (sorts the best first and says so in the note)
 *   selected  key of the selected city (highlighted)
 *   hot, onHot, pinned, onPin   city keys
 *   title, note, zero (include 0 on the axis; default true for '%')
 */
export default function DotStrip({
  rows = [], median = null, label = '', unit = '%', better = 'high', selected = null, hot = null, onHot, pinned, onPin,
  title, note, zero,
}) {
  const [ref, width] = useWidth()
  const [cur, setCur] = useState(-1)
  const fmt = fmtBy(unit)
  const have = rows.filter((r) => r.value != null).sort((a, b) => (better === 'low' ? a.value - b.value : b.value - a.value))
  const none = rows.filter((r) => r.value == null)
  const all = [...have, ...none]
  const rowH = 24
  const m = { l: 96, r: 16, t: 18, b: 26 }
  const height = m.t + m.b + rowH * all.length
  let [lo, hi] = extent([rows.map((r) => r.value), [median]], [0, 1])
  if (zero ?? unit === '%') lo = Math.min(0, lo)
  const { domain, ticks } = niceDomain(lo, hi, Math.max(2, Math.floor(width / 90)))
  const sx = linear(domain, [m.l, Math.max(m.l + 10, width - m.r)])
  const lit = litKeys(hot, pinned)
  const y = (i) => m.t + rowH * i + rowH / 2

  const setC = (i) => { setCur(i); onHot?.(i >= 0 ? all[i]?.key ?? null : null) }
  const onKey = (e) => {
    const map = { ArrowDown: 'ArrowRight', ArrowUp: 'ArrowLeft' }
    const n = stepIndex(map[e.key] || (e.key.startsWith('Arrow') ? null : e.key), cur, all.length, { big: 3 })
    if (n != null) { e.preventDefault(); setC(n) }
    if ((e.key === 'Enter' || e.key === ' ') && cur >= 0) { e.preventDefault(); onPin?.(all[cur].key) }
    if (e.key === 'Escape') setC(-1)
  }
  const shown = cur >= 0 ? all[cur] : all.find((r) => r.key === hot)
  const readout = shown ? `${shown.label}: ${fmt(shown.value)}${median != null && shown.value != null
    ? ` (mediana siedmiu miast ${fmt(median)})` : ''}` : ''
  const table = (
    <DataTableSimple caption={title || label} head={['Miasto', label]}
      rows={[...all.map((r) => [r.label, fmt(r.value)]), ['mediana siedmiu miast', fmt(median)]]} />
  )
  return (
    <ChartFrame title={title || label} readout={readout} table={table}
      note={note ?? `Kolejność: ${better === 'low' ? 'najmniej' : 'najwięcej'} u góry. Kilka punktów różnicy to nie ranking.`}>
      <div ref={ref} className="chx-plot">
        <svg width={width} height={height} role="img" tabIndex={0} className="chx-svg"
          aria-label={`${title || label}. Strzałki w górę i w dół wybierają miasto, Enter przypina.`}
          onKeyDown={onKey} onMouseLeave={() => setC(-1)}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={sx(v)} x2={sx(v)} y1={m.t} y2={height - m.b} className="chx-grid" />
              <text x={sx(v)} y={height - m.b + 14} textAnchor="middle" className="chx-tick">{unit === '%' ? fmtPct(v) : fmtNum(v, Number.isInteger(v) ? 0 : 1)}</text>
            </g>
          ))}
          {median != null ? (
            <g>
              <line x1={sx(median)} x2={sx(median)} y1={m.t - 2} y2={height - m.b} className="chx-median" />
              <text x={sx(median)} y={m.t - 6} textAnchor="middle" className="chx-floor-label">mediana {fmt(median)}</text>
            </g>
          ) : null}
          {all.map((r, i) => {
            const isSel = r.key === selected
            const on = lit.has(r.key) || i === cur
            const dim = lit.size > 0 && !on && !isSel
            return (
              <g key={r.key} opacity={dim ? 0.45 : 1} className="chx-row"
                onMouseEnter={() => setC(i)} onClick={() => onPin?.(r.key)}>
                <rect x={0} y={y(i) - rowH / 2} width={width} height={rowH} className={on ? 'chx-rowbg on' : 'chx-rowbg'} />
                <text x={m.l - 8} y={y(i)} dy="0.32em" textAnchor="end" className={isSel ? 'chx-label sel' : 'chx-label'}>{r.label}</text>
                {r.value == null
                  ? <text x={m.l} y={y(i)} dy="0.32em" className="chx-tick">{NO_DATA}</text>
                  : (
                    <>
                      <line x1={sx(Math.max(lo, Math.min(0, hi)))} x2={sx(r.value)} y1={y(i)} y2={y(i)} className="chx-stem" />
                      <circle cx={sx(r.value)} cy={y(i)} r={isSel ? 6 : 5}
                        fill={isSel ? SERIES_COLORS[0] : 'var(--kit-soft, #c3c9d4)'} stroke="var(--kit-panel, #1c1f26)" strokeWidth="2" />
                    </>
                  )}
              </g>
            )
          })}
        </svg>
      </div>
    </ChartFrame>
  )
}
