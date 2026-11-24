import { useEffect, useId, useRef, useState } from 'react'

/** Categorical colours for up to three highlighted series (validated on the dark panel #1c1f26: CVD and contrast). */
export const SERIES_COLORS = ['#3987e5', '#d95926', '#199e70']
/** Context series (not highlighted): recessive, not a category colour. */
export const CONTEXT_COLOR = 'var(--kit-faint, #6b7385)'

/** Width of an element, followed with ResizeObserver; `fallback` until measured (and during server rendering). */
export function useWidth(fallback = 560) {
  const ref = useRef(null)
  const [w, setW] = useState(fallback)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(([e]) => {
      const cw = Math.round(e.contentRect.width)
      if (cw > 0) setW(cw)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

/**
 * Common frame: title, optional note, a chart / table switch (aria-pressed), the plot or the table, and a
 * polite live region with the current read-out (what the pointer or the keyboard cursor points at).
 *
 * Props: title, note, readout (string), table (ReactNode), children (the SVG), view / onView (controlled, optional),
 *        legend (ReactNode, above the plot), className
 */
export default function ChartFrame({ title, note, readout, table, children, view, onView, legend, className = '' }) {
  const [own, setOwn] = useState('chart')
  const v = view || own
  const set = (x) => (onView ? onView(x) : setOwn(x))
  const id = useId()
  return (
    <figure className={`chx ${className}`} aria-labelledby={`${id}-t`}>
      <div className="chx-head">
        <figcaption id={`${id}-t`} className="chx-title">{title}</figcaption>
        <button
          type="button" className="chx-switch" aria-pressed={v === 'table'}
          onClick={() => set(v === 'table' ? 'chart' : 'table')}
        >
          {v === 'table' ? 'Wykres' : 'Tabela'}
        </button>
      </div>
      {legend && v === 'chart' ? <div className="chx-legend">{legend}</div> : null}
      {v === 'table' ? <div className="chx-tablewrap">{table}</div> : children}
      <p className="chx-readout" aria-live="polite">{v === 'chart' ? readout || ' ' : ' '}</p>
      {note ? <p className="chx-note">{note}</p> : null}
    </figure>
  )
}

/** Legend entry: a short line or a marker in the series colour and the name in text ink. */
export function LegendItem({ color, label, shape = 'line', dashed = false, onEnter, onLeave, onClick, lit }) {
  return (
    <button
      type="button" className={`chx-legend-item${lit === false ? ' dim' : ''}`}
      onMouseEnter={onEnter} onMouseLeave={onLeave} onFocus={onEnter} onBlur={onLeave} onClick={onClick}
    >
      <svg width="18" height="10" aria-hidden="true">
        {shape === 'line' && <line x1="1" x2="17" y1="5" y2="5" stroke={color} strokeWidth="2" strokeDasharray={dashed ? '3 2' : undefined} />}
        {shape === 'band' && <rect x="1" y="1" width="16" height="8" rx="2" fill={color} opacity=".3" />}
        {shape === 'dot' && <circle cx="9" cy="5" r="4" fill={color} />}
        {shape === 'ring' && <circle cx="9" cy="5" r="3.5" fill="none" stroke={color} strokeWidth="2" />}
        {shape === 'square' && <rect x="5" y="1" width="8" height="8" fill={color} />}
      </svg>
      <span>{label}</span>
    </button>
  )
}

/** Plain accessible table: head row and body rows of strings; the first cell of a row is its header. */
export function DataTableSimple({ caption, head, rows }) {
  return (
    <table className="chx-table">
      {caption ? <caption>{caption}</caption> : null}
      <thead><tr>{head.map((h, i) => <th key={i} scope="col">{h}</th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>{r.map((c, j) => (j === 0 ? <th key={j} scope="row">{c}</th> : <td key={j}>{c}</td>))}</tr>
        ))}
      </tbody>
    </table>
  )
}
