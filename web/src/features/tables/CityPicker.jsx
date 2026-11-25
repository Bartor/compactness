import { Modal } from '@bartor-net/ui-kit'

/**
 * The picker of single cities: a modal with a checkbox per agglomeration, the ones with timetables first. Changes apply at
 * once; `value` is the list now chosen, `onChange(list)` gets the new one (in the order of `everyCity`).
 */
export default function CityPicker({ everyCity, transport, names, value, onChange, onClose }) {
  const on = new Set(value)
  const toggle = (c, yes) => {
    const s = new Set(on)
    if (yes) s.add(c); else s.delete(c)
    onChange(everyCity.filter((x) => s.has(x)))
  }
  const part = (title, list) => list.length > 0 && (
    <section className="tb-picker-group" aria-label={title}>
      <h3>{title}</h3>
      <ul>
        {list.map((c) => (
          <li key={c}>
            <label className="tb-check">
              <input type="checkbox" checked={on.has(c)} onChange={(e) => toggle(c, e.target.checked)} />
              <span><b>{names[c] || c}</b></span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  )
  return (
    <Modal title="Wybierz miasta" onClose={onClose}>
      <div className="tb-picker">
        <div className="tb-picker-top">
          <span className="tb-count" role="status">wybrano {value.length} z {everyCity.length}</span>
          <button type="button" className="tb-btn tb-primary" onClick={onClose}>Gotowe</button>
        </div>
        {part('Z danymi o rozkładach jazdy', everyCity.filter((c) => transport.includes(c)))}
        {part('Tylko gęstość i forma (bez rozkładów)', everyCity.filter((c) => !transport.includes(c)))}
      </div>
    </Modal>
  )
}
