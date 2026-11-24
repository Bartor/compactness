import { useState } from 'react'
import ChartFrame, { DataTableSimple, SERIES_COLORS, useWidth } from './ChartFrame'
import { NO_DATA } from './format'
import { valuesTable } from './exportRows'
import { linear, litKeys, niceDomain, stepIndex } from './scales'

/** Rows of a ranked bar chart: those with a value sorted best first, the rest (no value) last. */
export function rankRows(rows, better = 'high') {
  const have = rows.filter((r) => r.value != null).sort((a, b) => (better === 'low' ? a.value - b.value : b.value - a.value))
  return [...have, ...rows.filter((r) => r.value == null)]
}

/**
 * One measure for many cities as horizontal bars that start at zero, best first, with the value written at the end
 * of each bar and the median marked. Larger than DotStrip (it is made for a page of its own). A row without a value
 * is not drawn as a bar: it is listed as "brak danych" (never as 0).
 *
 * Props
 *   rows      [{key, label, value}]; median (number | null); medianLabel (default "mediana")
 *   label     measure name (title and table head); unit is only for the caller's `format`
 *   format    value -> text (default: the number with a comma); tickFormat the same for the axis (default: format)
 *   better    'high' | 'low' | null: the order (null: highest first) and the note
 *   selected  key of the city the page was opened from (accent colour)
 *   colors    optional {key: colour} fixed by the app (as in the other charts)
 *   hot, onHot, pinned, onPin   city keys (hover lights, click pins)
 *   title, note, rowHeight
 */
export default function RankBars({
  rows = [], median = null, medianLabel = 'mediana', label = '', format, better = 'high', selected = null, colors,
  hot = null, onHot, pinned, onPin, title, note, rowHeight = 30, tickFormat, unit = '', exportInfo,
}) {
  const [ref, width] = useWidth()
  const [cur, setCur] = useState(-1)
  const fmt = format || ((v) => (v == null ? NO_DATA : new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 2 }).format(v)))
  const tick = tickFormat || fmt
  const all = rankRows(rows, better)
  const m = { l: 130, r: 110, t: 24, b: 28 }
  const height = m.t + m.b + rowHeight * all.length
  const vals = rows.map((r) => r.value).filter((v) => v != null)
  const hi = Math.max(0, median ?? 0, ...vals)
  const lo = Math.min(0, ...vals)
  const { domain, ticks } = niceDomain(lo, hi > lo ? hi : lo + 1, Math.max(2, Math.floor(width / 110)))
  const sx = linear(domain, [m.l, Math.max(m.l + 20, width - m.r)])
  const lit = litKeys(hot, pinned)
  const y = (i) => m.t + rowHeight * i + rowHeight / 2
  const colour = (r) => colors?.[r.key] || (r.key === selected ? SERIES_COLORS[0] : 'var(--kit-link, #7aa2e3)')

  const setC = (i) => { setCur(i); onHot?.(i >= 0 ? all[i]?.key ?? null : null) }
  const onKey = (e) => {
    const map = { ArrowDown: 'ArrowRight', ArrowUp: 'ArrowLeft' }
    const n = stepIndex(map[e.key] || (e.key.startsWith('Arrow') ? null : e.key), cur, all.length, { big: 3 })
    if (n != null) { e.preventDefault(); setC(n) }
    if ((e.key === 'Enter' || e.key === ' ') && cur >= 0) { e.preventDefault(); onPin?.(all[cur].key) }
    if (e.key === 'Escape') setC(-1)
  }
  const shown = cur >= 0 ? all[cur] : all.find((r) => r.key === hot)
  const readout = shown ? `${shown.label}: ${fmt(shown.value)}${median != null && shown.value != null ? ` (${medianLabel} ${fmt(median)})` : ''}` : ''
  const table = (
    <DataTableSimple
      caption={title || label} head={['Miasto', label]}
      rows={[...all.map((r) => [r.label, fmt(r.value)]), ...(median != null ? [[medianLabel, fmt(median)]] : [])]}
    />
  )
  const order = better === 'low' ? 'najmniejsza wartość u góry' : 'największa wartość u góry'
  return (
    <ChartFrame
      title={title || label} readout={readout} table={table} className="chx-rankbars" exportInfo={exportInfo}
      exportData={() => valuesTable(all, { label: label || 'wartość', unit, median, medianLabel })}
      note={note ?? `Słupki zaczynają się od zera; ${order}. Kilka punktów różnicy to nie ranking.`}
    >
      <div ref={ref} className="chx-plot">
        <svg
          width={width} height={height} role="img" tabIndex={0} className="chx-svg"
          aria-label={`${title || label}. Strzałki w górę i w dół wybierają miasto, Enter przypina.`}
          onKeyDown={onKey} onMouseLeave={() => setC(-1)}
        >
          {ticks.map((v) => (
            <g key={v}>
              <line x1={sx(v)} x2={sx(v)} y1={m.t} y2={height - m.b} className="chx-grid" />
              <text x={sx(v)} y={height - m.b + 16} textAnchor="middle" className="chx-tick">{tick(v)}</text>
            </g>
          ))}
          {all.map((r, i) => {
            const isSel = r.key === selected
            const on = lit.has(r.key) || i === cur
            const dim = lit.size > 0 && !on && !isSel
            const x0 = sx(Math.max(domain[0], Math.min(0, domain[1])))
            return (
              <g
                key={r.key} opacity={dim ? 0.45 : 1} className="chx-row"
                onMouseEnter={() => setC(i)} onClick={() => onPin?.(r.key)}
              >
                <rect x={0} y={y(i) - rowHeight / 2} width={width} height={rowHeight} className={on ? 'chx-rowbg on' : 'chx-rowbg'} />
                <text x={m.l - 10} y={y(i)} dy="0.32em" textAnchor="end" className={isSel ? 'chx-label sel' : 'chx-label'} style={{ fontSize: 14 }}>{r.label}</text>
                {r.value == null
                  ? <text x={m.l} y={y(i)} dy="0.32em" className="chx-tick" style={{ fontSize: 13 }}>{NO_DATA}</text>
                  : (
                    <>
                      <rect
                        x={Math.min(x0, sx(r.value))} y={y(i) - rowHeight * 0.32} width={Math.max(1, Math.abs(sx(r.value) - x0))}
                        height={rowHeight * 0.64} rx={3} fill={colour(r)} opacity={isSel || on ? 1 : 0.85}
                      />
                      <text
                        x={Math.max(x0, sx(r.value)) + 8} y={y(i)} dy="0.32em" className="chx-label"
                        style={{ fontSize: 14, fontWeight: isSel || on ? 700 : 500, fontVariantNumeric: 'tabular-nums' }}
                      >{fmt(r.value)}</text>
                    </>
                  )}
              </g>
            )
          })}
          {median != null ? (
            <g>
              <line x1={sx(median)} x2={sx(median)} y1={m.t - 4} y2={height - m.b} className="chx-median" />
              <text x={sx(median)} y={m.t - 9} textAnchor="middle" className="chx-floor-label">{medianLabel} {fmt(median)}</text>
            </g>
          ) : null}
        </svg>
      </div>
    </ChartFrame>
  )
}
