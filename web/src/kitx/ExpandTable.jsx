import { useState } from 'react'
import { HelpButton } from '@bartor-net/ui-kit'

/**
 * A table of figures with grouped rows, a "?" on every row (and, when given, on a column head) that unfolds an
 * explanation in place, several at once, and a column that can be lit from outside. Kit-like: depends only on the
 * kit and on its own CSS (kitx.css), not on anything of this app, so it can move into the kit.
 *
 * Props
 *   columns   [{key, head, title?, help?, onPick?, narrow?}]
 *               head    text of the column head; title: its tooltip (the full name)
 *               help    explanation behind a "?" in the head
 *               onPick  makes the head a button
 *               narrow  a thin column (a rank, say)
 *   groups    [{id, title, rows: [{id, label, unit?, help?, action?, cells}]}]
 *               label   the row's name; unit: dim text after it
 *               help    explanation behind the row's "?"; without it there is no "?"
 *               action  {label, onClick}: a small link-like button under the label
 *               cells   one per column: {text, tone?, title?}; tone is 'best' (bold), 'weak' or 'dim' (muted)
 *   hot       key of the column to light, or null
 *   onHot     (key | null) => void, called when the pointer or focus enters or leaves a column
 *   labelHead text over the first column
 *   caption   accessible name of the scrolling region
 */
export default function ExpandTable({ columns, groups, hot = null, onHot, labelHead = 'Miara', caption }) {
  const [openRows, setOpenRows] = useState(() => new Set())
  const [openCols, setOpenCols] = useState(() => new Set())
  const flip = (set, setSet, k) => setSet((prev) => {
    const next = new Set(prev)
    if (next.has(k)) next.delete(k)
    else next.add(k)
    return next
  })
  const span = columns.length + 1
  const colClass = (c) => ['kitx-col', c.narrow && 'narrow', hot != null && hot === c.key && 'hot'].filter(Boolean).join(' ')
  const hover = (key) => ({
    onMouseEnter: () => onHot?.(key), onMouseLeave: () => onHot?.(null),
  })
  const openHeads = columns.filter((c) => c.help && openCols.has(c.key))

  return (
    <div className="kitx-scroll" role="region" aria-label={caption} tabIndex={0}>
      <table className="kitx-table">
        <thead>
          <tr>
            <th scope="col" className="kitx-label-head">{labelHead}</th>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={colClass(c)} title={c.title} {...hover(c.key)}>
                <span className="kitx-head">
                  {c.onPick
                    ? (
                      <button type="button" className="kitx-colbtn" onClick={c.onPick}
                        onFocus={() => onHot?.(c.key)} onBlur={() => onHot?.(null)}>{c.head}</button>
                    )
                    : c.head}
                  {c.help && <HelpButton open={openCols.has(c.key)} onClick={() => flip(openCols, setOpenCols, c.key)} />}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {openHeads.length > 0 && (
            <tr className="kitx-help-row">
              <td colSpan={span}>
                <div className="kitx-help">
                  {openHeads.map((c) => <div key={c.key}><b>{c.title || c.head}</b>{c.help}</div>)}
                </div>
              </td>
            </tr>
          )}
          {groups.map((g) => [
            <tr key={`${g.id}:h`} className="kitx-group">
              <th scope="colgroup" colSpan={span}>{g.title}</th>
            </tr>,
            ...g.rows.flatMap((r) => {
              const k = `${g.id}/${r.id}`
              const open = !!r.help && openRows.has(k)
              const out = [
                <tr key={k}>
                  <th scope="row" className="kitx-label">
                    <span className="kitx-name">
                      <span>{r.label}{r.unit && <small className="kitx-unit"> {r.unit}</small>}</span>
                      {r.help && <HelpButton open={open} onClick={() => flip(openRows, setOpenRows, k)} />}
                    </span>
                    {r.action && (
                      <button type="button" className="kitx-action" onClick={r.action.onClick}>{r.action.label}</button>
                    )}
                  </th>
                  {columns.map((c, i) => {
                    const cell = r.cells[i] || { text: '–', tone: 'dim' }
                    return (
                      <td key={c.key} className={`${colClass(c)}${cell.tone ? ` kitx-${cell.tone}` : ''}`}
                        title={cell.title} {...hover(c.key)}>{cell.text}</td>
                    )
                  })}
                </tr>,
              ]
              if (open) {
                out.push(
                  <tr key={`${k}:help`} className="kitx-help-row">
                    <td colSpan={span}><div className="kitx-help">{r.help}</div></td>
                  </tr>,
                )
              }
              return out
            }),
          ])}
        </tbody>
      </table>
    </div>
  )
}
