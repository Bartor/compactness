import { useEffect, useMemo, useRef, useState } from 'react'
import { Modal } from '@bartor-net/ui-kit'
import { METRIC_INFO } from '../../metricInfo'
import { buildGroups, metricName } from '../../metricTable'
import { firstSentence } from '../../helpText'

const norm = (s) => String(s || '').toLocaleLowerCase('pl-PL')

/** A checkbox that can show "some of the group". */
function GroupBox({ checked, some, onChange, label }) {
  const ref = useRef(null)
  useEffect(() => { if (ref.current) ref.current.indeterminate = some && !checked }, [some, checked])
  return (
    <label className="tb-check tb-check-group">
      <input ref={ref} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  )
}

/**
 * The picker of the measures: a modal with the groups as headings (each with "cała grupa"), a checkbox, the name and a
 * one-line description for every measure, a search by name, a count, "Wyczyść" and "Gotowe". Changes apply at once (the
 * table behind it follows); `ids` is the list now selected, `onChange(ids)` gets the new one.
 */
export default function MeasurePicker({ index, ids, onChange, onClose, info = METRIC_INFO }) {
  const [text, setText] = useState('')
  const inputRef = useRef(null)
  const all = useMemo(() => buildGroups(index), [index])
  const total = all.reduce((n, g) => n + g.metrics.length, 0)
  const on = new Set(ids)
  const q = norm(text.trim())
  const shown = all
    .map((g) => ({ ...g, rows: g.metrics.map((id) => ({ id, name: metricName(index, id, info) })).filter((r) => !q || norm(r.name).includes(q)) }))
    .filter((g) => g.rows.length > 0)
  useEffect(() => { inputRef.current?.focus() }, [])

  const set = (list) => onChange(all.flatMap((g) => g.metrics).filter((id) => list.has(id)))
  const toggle = (id, yes) => { const s = new Set(on); if (yes) s.add(id); else s.delete(id); set(s) }
  const toggleGroup = (g, yes) => { const s = new Set(on); g.rows.forEach((r) => (yes ? s.add(r.id) : s.delete(r.id))); set(s) }

  return (
    <Modal title="Wybierz miary" onClose={onClose}>
      <div className="tb-picker">
        <div className="tb-picker-top">
          <input
            ref={inputRef} type="search" className="tb-search" value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Szukaj miary po nazwie" aria-label="Szukaj miary po nazwie"
          />
          <span className="tb-count" role="status">wybrano {ids.length} z {total}</span>
          <button type="button" className="tb-btn" onClick={() => onChange([])} disabled={ids.length === 0}>Wyczyść</button>
          <button type="button" className="tb-btn tb-primary" onClick={onClose}>Gotowe</button>
        </div>
        {shown.length === 0 && <p className="tb-none">Żadna miara nie pasuje do „{text}”.</p>}
        {shown.map((g) => {
          const n = g.rows.filter((r) => on.has(r.id)).length
          return (
            <section key={g.id} className="tb-picker-group" aria-label={g.title}>
              <h3>
                {g.title}
                <GroupBox
                  checked={n === g.rows.length} some={n > 0} onChange={(yes) => toggleGroup(g, yes)}
                  label={`cała grupa${q ? ' (pokazane)' : ''}`}
                />
              </h3>
              <ul>
                {g.rows.map((r) => (
                  <li key={r.id}>
                    <label className="tb-check">
                      <input type="checkbox" checked={on.has(r.id)} onChange={(e) => toggle(r.id, e.target.checked)} />
                      <span>
                        <b>{r.name}</b>
                        <small>{firstSentence(info[r.id]?.read?.[0], 120)}</small>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>
    </Modal>
  )
}
