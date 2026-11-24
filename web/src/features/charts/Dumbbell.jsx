import { useState } from 'react'
import ChartFrame, { DataTableSimple, LegendItem, SERIES_COLORS, useWidth } from './ChartFrame'
import { fmtNum, fmtPct, fmtPts, NO_DATA } from './format'
import { pairTable } from './exportRows'
import { extent, linear, litKeys, niceDomain, stepIndex } from './scales'

/**
 * Paired values per city: two ends joined by a bar (30 vs 45 min, peak vs evening, core vs urban centre).
 * End a is a ring, end b a filled dot (shape as well as colour). Rows keep the fixed city order unless sort='a'|'b'|'gap'.
 *
 * Props
 *   rows      [{key, label, a, b}]; aLabel, bLabel; unit ('%' or text)
 *   selected  key of the selected city (bold label); sort
 *   hot, onHot, pinned, onPin   city keys
 *   title, note
 */
export default function Dumbbell({
  rows = [], aLabel = 'a', bLabel = 'b', unit = '%', selected = null, sort = null, hot = null, onHot, pinned, onPin,
  title = '', note, exportInfo,
}) {
  const [ref, width] = useWidth()
  const [cur, setCur] = useState(-1)
  const fmt = (v) => (unit === '%' ? fmtPct(v, 1) : v == null ? NO_DATA : `${fmtNum(v, 1)} ${unit}`)
  const val = (r) => (sort === 'gap' ? (r.b ?? 0) - (r.a ?? 0) : r[sort] ?? -Infinity)
  const list = sort ? [...rows].sort((p, q) => val(q) - val(p)) : rows
  const rowH = 24
  const m = { l: 96, r: 16, t: 8, b: 26 }
  const height = m.t + m.b + rowH * list.length
  let [lo, hi] = extent([rows.map((r) => r.a), rows.map((r) => r.b)], [0, 1])
  if (unit === '%') lo = Math.min(0, lo)
  const { domain, ticks } = niceDomain(lo, hi, Math.max(2, Math.floor(width / 90)))
  const sx = linear(domain, [m.l, Math.max(m.l + 10, width - m.r)])
  const lit = litKeys(hot, pinned)
  const y = (i) => m.t + rowH * i + rowH / 2
  const ca = SERIES_COLORS[0]; const cb = SERIES_COLORS[1]

  const setC = (i) => { setCur(i); onHot?.(i >= 0 ? list[i]?.key ?? null : null) }
  const onKey = (e) => {
    const map = { ArrowDown: 'ArrowRight', ArrowUp: 'ArrowLeft' }
    const n = stepIndex(map[e.key] || (e.key.startsWith('Arrow') ? null : e.key), cur, list.length, { big: 3 })
    if (n != null) { e.preventDefault(); setC(n) }
    if ((e.key === 'Enter' || e.key === ' ') && cur >= 0) { e.preventDefault(); onPin?.(list[cur].key) }
    if (e.key === 'Escape') setC(-1)
  }
  const shown = cur >= 0 ? list[cur] : list.find((r) => r.key === hot)
  const gap = (r) => (r.a != null && r.b != null ? (unit === '%' ? fmtPts(r.b - r.a) : fmtNum(r.b - r.a, 1)) : NO_DATA)
  const readout = shown ? `${shown.label}: ${aLabel} ${fmt(shown.a)}, ${bLabel} ${fmt(shown.b)} (różnica ${gap(shown)})` : ''
  const legend = (
    <>
      <LegendItem color={ca} shape="ring" label={aLabel} />
      <LegendItem color={cb} shape="dot" label={bLabel} />
    </>
  )
  const table = (
    <DataTableSimple caption={title} head={['Miasto', aLabel, bLabel, 'Różnica']}
      rows={list.map((r) => [r.label, fmt(r.a), fmt(r.b), gap(r)])} />
  )
  return (
    <ChartFrame
      title={title} note={note} readout={readout} table={table} legend={legend} exportInfo={exportInfo}
      exportData={() => pairTable(list, { aLabel, bLabel, unit })}
    >
      <div ref={ref} className="chx-plot">
        <svg width={width} height={height} role="img" tabIndex={0} className="chx-svg"
          aria-label={`${title}. Strzałki w górę i w dół wybierają miasto, Enter przypina.`}
          onKeyDown={onKey} onMouseLeave={() => setC(-1)}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={sx(v)} x2={sx(v)} y1={m.t} y2={height - m.b} className="chx-grid" />
              <text x={sx(v)} y={height - m.b + 14} textAnchor="middle" className="chx-tick">{unit === '%' ? fmtPct(v) : fmtNum(v)}</text>
            </g>
          ))}
          {list.map((r, i) => {
            const on = lit.has(r.key) || i === cur
            const dim = lit.size > 0 && !on && r.key !== selected
            return (
              <g key={r.key} opacity={dim ? 0.45 : 1} className="chx-row" onMouseEnter={() => setC(i)} onClick={() => onPin?.(r.key)}>
                <rect x={0} y={y(i) - rowH / 2} width={width} height={rowH} className={on ? 'chx-rowbg on' : 'chx-rowbg'} />
                <text x={m.l - 8} y={y(i)} dy="0.32em" textAnchor="end" className={r.key === selected ? 'chx-label sel' : 'chx-label'}>{r.label}</text>
                {r.a != null && r.b != null ? <line x1={sx(r.a)} x2={sx(r.b)} y1={y(i)} y2={y(i)} className="chx-bar" /> : null}
                {r.a == null && r.b == null ? <text x={m.l} y={y(i)} dy="0.32em" className="chx-tick">{NO_DATA}</text> : null}
                {r.a != null ? <circle cx={sx(r.a)} cy={y(i)} r="4.5" fill="var(--kit-panel, #1c1f26)" stroke={ca} strokeWidth="2.5" /> : null}
                {r.b != null ? <circle cx={sx(r.b)} cy={y(i)} r="5" fill={cb} stroke="var(--kit-panel, #1c1f26)" strokeWidth="1.5" /> : null}
              </g>
            )
          })}
        </svg>
      </div>
    </ChartFrame>
  )
}
