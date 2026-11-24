import { Chips, DataTable } from '@bartor-net/ui-kit'
import { useState } from 'react'
import './speed.css'
import { CLASS_COLORS, CLASS_LABELS, MODE_PL, SCHEDULED, bandText, classOf } from './speedModel'
import {
  DAY_FILTERS, DEFAULT_FILTERS, MODE_FILTERS, bandsOfDay, cellValue, defaultOrder, filterRows, hotRowKeys,
  normaliseFilters, rowIdFromTarget, setFilter,
} from './lineTable'

const nf = (v, d = 1) => new Intl.NumberFormat('pl-PL', { maximumFractionDigits: d, useGrouping: 'always' }).format(v)
const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
const MISSING = { content: '–', tone: 'dim', title: 'brak danych' }

/**
 * The lines table of the scheduled-speed view: the kit's DataTable sorted by column, with filters (city, mode, day
 * type, band) and a two-way link with the map.
 *
 *   data       parseLines(lines.json)
 *   cityNames  {agg: name}
 *   filters / onFilters   controlled filters ({city, mode, day, band}); without them the table keeps its own
 *   hot        row keys ("agg|feed|line") to light (from the map); onHot(keys | null) when the pointer enters a row
 *   pinned     pinned row keys; onPin(key) on a click or Enter on a row's line button
 */
export default function SpeedTable({ data, cityNames = {}, filters, onFilters, hot = null, onHot, pinned = [], onPin }) {
  const [own, setOwn] = useState(DEFAULT_FILTERS)
  const f = normaliseFilters(filters ?? own)
  const change = (name, value) => {
    const next = setFilter(f, name, value)
    if (onFilters) onFilters(next)
    else setOwn(next)
  }
  const rows = defaultOrder(filterRows(data?.rows || [], f))
  const lit = hotRowKeys(rows, hot)
  const cities = Object.keys(cityNames)

  const columns = [
    ...(f.city ? [] : [{ key: 'agg', head: 'Miasto', align: 'left', first: 'asc' }]),
    { key: 'mode', head: 'Środek', align: 'left', first: 'asc' },
    { key: 'term', head: 'Trasa', align: 'left', first: 'asc' },
    { key: 'v', head: 'km/h', title: `Prędkość z rozkładu, ${bandText(f.band)}` },
    { key: 'gap', head: 'wieczór − szczyt', title: 'Środa: wieczór 20–23 minus szczyt poranny 07–09, km/h' },
    { key: 'n', head: 'kursy', title: 'Kursy rozpoczęte w paśmie (oba kierunki)' },
    { key: 'hw', head: 'co ile min', title: 'Odstęp w paśmie, kierunek z większą liczbą kursów', first: 'asc' },
    { key: 'sp', head: 'przyst. co m', title: 'Średnia odległość między przystankami (środa)' },
    { key: 'flags', head: 'uwagi', align: 'left', sortable: false },
  ]
  const cell = (r, key) => {
    const v = cellValue(r, key, f.band)
    if (key === 'agg') return { content: cityNames[r.agg] || r.agg, value: cityNames[r.agg] || r.agg }
    if (key === 'mode') return { content: MODE_PL[r.mode] || r.mode, value: r.mode }
    if (key === 'term') return { content: r.term || '–', value: r.term || '' }
    if (key === 'flags') return r.flags ? { content: '!', title: r.flags, tone: 'weak' } : null
    if (!isNum(v)) return MISSING
    if (key === 'v') {
      const c = classOf(v)
      return {
        content: <span className="speed-cell"><i className="speed-swatch" style={{ background: CLASS_COLORS[c] }} />{nf(v)}</span>,
        value: v, title: `${nf(v)} km/h, klasa ${CLASS_LABELS[c]} (${SCHEDULED})`,
      }
    }
    if (key === 'gap') return { content: `${v > 0 ? '+' : ''}${nf(v)}`, value: v }
    return { content: nf(v, key === 'n' || key === 'sp' ? 0 : 1), value: v }
  }
  const tableRows = rows.map((r) => {
    const on = pinned.includes(r.key)
    return {
      id: r.key,
      name: `linia ${r.line}`,
      labelValue: r.line,
      label: (
        <button
          type="button" className={['speed-line', on && 'pinned', lit.has(r.key) && 'hot'].filter(Boolean).join(' ')}
          data-row-id={r.key} aria-pressed={on}
          onFocus={() => onHot?.([r.key])} onBlur={() => onHot?.(null)}
          onClick={(e) => { e.stopPropagation(); onPin?.(r.key) }}
        >{r.line}</button>
      ),
      cells: columns.map((c) => cell(r, c.key)),
    }
  })

  const over = (e) => {
    const id = rowIdFromTarget(e.target)
    if (id) onHot?.([id])
  }
  const click = (e) => {
    const id = rowIdFromTarget(e.target)
    if (id && !(e.target.closest && e.target.closest('button,a'))) onPin?.(id)
  }

  return (
    <div className="speed-table">
      <div className="speed-filters">
        {cities.length > 0 && (
          <Chips
            items={[{ key: '', label: 'wszystkie miasta', on: !f.city }, ...cities.map((c) => ({ key: c, label: cityNames[c], on: f.city === c }))]}
            onPick={(k) => change('city', k || null)} tight
          />
        )}
        <Chips items={MODE_FILTERS.map((m) => ({ key: m.key, label: m.label, on: m.key === f.mode }))} onPick={(k) => change('mode', k)} tight />
        <Chips items={DAY_FILTERS.map((d) => ({ key: d.key, label: d.label, on: d.key === f.day }))} onPick={(k) => change('day', k)} tight />
        <Chips items={bandsOfDay(f.day).map((b) => ({ key: b.key, label: b.label, on: b.key === f.band }))} onPick={(k) => change('band', k)} tight />
      </div>
      <p className="speed-caption">
        {`${rows.length} linii kursujących w paśmie ${bandText(f.band)}. Prędkość komunikacyjna z rozkładu (z postojami), `
          + `${SCHEDULED}. Wskaż wiersz, aby zobaczyć odcinki linii na mapie; kliknij numer, aby je zostawić.`}
      </p>
      {/* the wrapper only listens: hovering anywhere in a row lights the line on the map */}
      <div onMouseOver={over} onMouseLeave={() => onHot?.(null)} onClick={click}>
        <DataTable
          columns={columns} rows={tableRows} caption="Prędkość linii z rozkładu" labelHead="Linia"
          sortBy="column" empty="–"
        />
      </div>
    </div>
  )
}
