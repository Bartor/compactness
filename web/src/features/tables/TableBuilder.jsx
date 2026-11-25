import { useEffect, useState } from 'react'
import { DataTable, Hint, LinkButton, Modal } from '@bartor-net/ui-kit'
import { DOMAIN_INFO } from '../../metricInfo'
import { AREAS } from '../../metricTable'
import ExportButtons from '../../export/ExportButtons'
import { tableExport } from '../../export/shape'
import { buildTable, orderedRecords } from './buildTable'
import MeasurePicker from './MeasurePicker'
import CityPicker from './CityPicker'
import { readOwn, writeOwn } from './storage'
import {
  PRESET_GROUPS, SET_ALL, SET_OWN, SET_STORY, areasOf, citiesMode, citiesOf, normalizeTable, selectionOf, shapeOf,
  toggleArea,
} from './spec'
import './tables.css'

const areaShort = (a) => DOMAIN_INFO[a]?.short || a

function Chip({ on, onClick, children, title, follow = false }) {
  return (
    <button type="button" className={`tb-chip${on ? ' on' : ''}${follow ? ' follow' : ''}`} aria-pressed={on} title={title} onClick={onClick}>
      {children}
    </button>
  )
}

/**
 * The configurable table of measures: a one-line bar (which measures, which cities, which areas) over one DataTable, used by
 * the comparison (`agg` null) and by a city's view (`agg` the city). `table` is the state of spec.js and `onTable` gets the
 * next one; the address and the browser's storage are kept by the caller and by this component respectively. Nothing in
 * the bar changes its height with its own state: what is said about the result is under the table, and the sort line is a
 * fixed-width slot of the bar, there with or without a sort.
 */
export default function TableBuilder({
  index, everyCity, transport, names, globalArea, agg = null, table, onTable, layers, onShowLayer, onOpenMetric, onPickCity,
  hot, setHot, sort = null, setSort, wide = true, onOpenLimits,
}) {
  const [picker, setPicker] = useState(null)   // 'bar' (a phone) | 'measures' | 'cities' | null
  const [ownSort, setOwnSort] = useState(null)
  const keeps = typeof setSort === 'function' || sort != null
  const sortNow = keeps ? sort : ownSort
  const onSort = typeof setSort === 'function' ? setSort : setOwnSort
  const t = normalizeTable(table)
  const selection = selectionOf(t, index)
  const cities = citiesOf(t, { agg, everyCity, transport, index, ids: selection.ids })
  const { areas, following } = areasOf(t, { globalArea, agg })
  const shape = shapeOf(cities, areas, t.swap)
  const grouped = !sortNow?.key
  const mode = citiesMode(cities, { agg, everyCity, transport })

  useEffect(() => { if (t.set === SET_OWN) writeOwn(t.ids) }, [t.set, t.ids.join(',')])   // eslint-disable-line react-hooks/exhaustive-deps

  const model = buildTable({
    index, selection, cities, areas, shape, names, layers, onShowLayer, onOpenMetric, onPickCity, transport, everyCity, grouped,
  })

  // a choice equal to what the view would do without it is not kept, so the address stays short
  const settle = (next) => {
    const n = normalizeTable(next)
    const sel = selectionOf(n, index)
    if (n.cities) {
      const same = citiesOf({ ...n, cities: null }, { agg, everyCity, transport, index, ids: sel.ids })
      const mine = citiesOf(n, { agg, everyCity, transport, index, ids: sel.ids })
      if (same.length === mine.length && same.every((c) => mine.includes(c))) n.cities = null
    }
    onTable(n)
  }
  const patch = (p) => settle({ ...t, ...p })
  const ownIds = t.set === SET_OWN ? t.ids : readOwn().filter((id) => index[id])
  const pickSet = (set) => patch({ set, ids: [] })
  const pickOwn = () => {
    if (t.set === SET_OWN) { setPicker('measures'); return }
    if (ownIds.length) patch({ set: SET_OWN, ids: ownIds })
    else setPicker('measures')
  }
  const toggleSwap = () => patch({ swap: !t.swap })

  const sortRow = sortNow?.key ? model.groups.flatMap((g) => g.rows).find((r) => r.id === sortNow.key) : null
  const sortLine = (() => {
    if (shape.cols !== 'cities') return <span className="tb-sortline">Kolumny: {shape.cols === 'areas' ? 'obszary' : 'wartość i miejsce'}</span>
    if (!sortRow) return <span className="tb-sortline" title="Kliknij nazwę miary w tabeli, aby ułożyć aglomeracje według niej">Kolejność: domyślna</span>
    const bestFirst = sortRow.better && sortNow.dir === (sortRow.better === 'lower' ? 'asc' : 'desc')
    const full = `Aglomeracje według: ${sortRow.name}, ${sortNow.dir === 'desc' ? 'od największej' : 'od najmniejszej'} wartości${bestFirst ? ' (najlepsze pierwsze)' : ''}`
    return (
      <span className="tb-sortline" title={full}>
        <span className="tb-sorttext">Wg: <b>{sortRow.name}</b> {sortNow.dir === 'desc' ? '↓' : '↑'}</span> <LinkButton onClick={() => onSort(null)}>domyślna</LinkButton>
      </span>
    )
  })()

  const caption = `Miary: ${cities.length === 1 ? names[cities[0]] || cities[0] : `${cities.length} aglomeracji`}, ${areas.map(areaShort).join(', ')}`
  const areaNote = areas.length === 1
    ? <>Liczby dotyczą obszaru „{areaShort(areas[0])}”{following ? ' (przełącznik u góry strony)' : ''}.</>
    : <>Obszary: {areas.map(areaShort).join(', ')}.</>
  const lack = model.lackTimetable.map((c) => names[c] || c)
  const rows = model.flat ? model.groups.flatMap((g) => g.rows) : null

  const table_ = selection.ids.length === 0
    ? (
      <div className="tb-empty">
        <Hint>
          {t.set === SET_OWN
            ? 'Wybierz miary, aby zobaczyć tabelę: użyj przycisku „Wybierz miary…” albo jednego z gotowych zestawów powyżej.'
            : 'Ten zestaw nie ma jeszcze liczb w danych.'}
        </Hint>
      </div>
    )
    : model.rowCount === 0
      ? (
        <div className="tb-empty">
          <Hint>
            Dla wybranych miast i obszarów te miary nie mają liczb.
            {lack.length > 0 && ` Brak danych o rozkładach jazdy: ${lack.join(', ')}.`} Wybierz inne miasta lub obszary albo inny zestaw miar.
          </Hint>
        </div>
      )
      : (
        <DataTable
          caption={caption} labelHead="Miara" className={`tb-table ${wide ? 'dock-table' : 'compare-table'}`}
          columns={model.columns} {...(rows ? { rows } : { groups: model.groups })}
          sortBy={shape.cols === 'cities' ? 'row' : undefined} sort={sortNow} onSortChange={onSort}
          hot={shape.cols === 'cities' ? hot : undefined} onHot={shape.cols === 'cities' ? setHot : undefined}
          resizable={wide ? 'all' : false} widthsKey={`compactness-tbl-${shape.key}`} density={wide ? 'compact' : 'regular'}
          labelWidth={wide ? { min: '17rem', max: '24rem' } : { min: '11.5rem', max: '12rem' }}
        />
      )

  const segMeasures = (
    <div className="tb-seg">
      <span className="tb-lab">Miary</span>
      <Chip on={t.set === SET_STORY} onClick={() => pickSet(SET_STORY)} title="Dziesięć miar, które opowiadają całą historię">Najważniejsze</Chip>
      <Chip on={t.set === SET_ALL} onClick={() => pickSet(SET_ALL)} title="Wszystkie miary, pogrupowane">Wszystkie</Chip>
      <select
        className={`tb-select${PRESET_GROUPS.some((g) => g.id === t.set) ? ' on' : ''}`} aria-label="Zestaw miar: jedna grupa"
        value={PRESET_GROUPS.some((g) => g.id === t.set) ? t.set : ''} onChange={(e) => e.target.value && pickSet(e.target.value)}
      >
        <option value="">Grupa miar…</option>
        {PRESET_GROUPS.map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
      </select>
      <Chip on={t.set === SET_OWN} onClick={pickOwn} title="Własny wybór miar (zapamiętany w tej przeglądarce)">Własny{t.set === SET_OWN ? ` (${selection.ids.length})` : ''}</Chip>
      <button type="button" className="tb-btn" onClick={() => setPicker('measures')}>Wybierz miary…</button>
    </div>
  )
  const segCities = (
    <div className="tb-seg">
      <span className="tb-lab">Miasta</span>
      {agg && <Chip on={mode === 'own'} onClick={() => patch({ cities: null })}>{names[agg] || agg}</Chip>}
      <Chip on={mode === 'tt'} onClick={() => patch({ cities: 'tt' })} title="Aglomeracje, dla których mamy rozkłady jazdy">{transport.length} z rozkładami</Chip>
      <Chip on={mode === 'all'} onClick={() => patch({ cities: 'all' })}>Wszystkie {everyCity.length}</Chip>
      <Chip on={mode === 'pick'} onClick={() => setPicker('cities')} title="Wybierz pojedyncze miasta">Wybrane…{mode === 'pick' ? ` (${cities.length})` : ''}</Chip>
    </div>
  )
  const segAreas = (
    <div className="tb-seg" title="Dotyczy tylko tej tabeli; przełącznik „Obszar” u góry strony zmienia resztę strony">
      <span className="tb-lab">Obszary</span>
      {AREAS.map((a) => (
        <Chip key={a} on={areas.includes(a)} follow={following} onClick={() => patch({ areas: toggleArea(areas, a) })}>{areaShort(a)}</Chip>
      ))}
      <span className="tb-follow">
        {following
          ? 'jak u góry'
          : <LinkButton onClick={() => patch({ areas: null })}>jak u góry</LinkButton>}
      </span>
    </div>
  )
  const swapBtn = (
    <button
      type="button" className={`tb-btn${t.swap && shape.canSwap ? ' on' : ''}`} aria-pressed={t.swap && shape.canSwap} disabled={!shape.canSwap}
      aria-label="Zamień wiersze i kolumny" onClick={toggleSwap}
      title={shape.canSwap ? 'Zamień wiersze i kolumny: miasta w kolumnach z obszarami w wierszach, albo odwrotnie' : 'Zamień wiersze i kolumny: dostępne, gdy wybrano kilka miast i kilka obszarów'}
    >
      ⇄ Zamień
    </button>
  )
  const exportEl = (
    <span className="tb-export">
      <ExportButtons
        table={() => tableExport({ records: orderedRecords(model, sortNow), names, index })}
        name={{ view: agg ? 'miasto' : 'porownanie', subject: agg ? names[agg] || agg : 'miary', area: areas.length === 1 ? areas[0] : 'obszary' }}
      />
    </span>
  )
  // a phone: one line that says what the table shows; the controls are in a modal (nothing opens in the page and pushes the table)
  const summary = [
    t.set === SET_OWN ? `Własny (${selection.ids.length})` : t.set === SET_STORY ? 'Najważniejsze' : t.set === SET_ALL ? 'Wszystkie miary' : PRESET_GROUPS.find((g) => g.id === t.set)?.title,
    mode === 'tt' ? `${cities.length} z rozkładami` : mode === 'all' ? `Wszystkie ${cities.length}` : cities.length === 1 ? names[cities[0]] || cities[0] : `${cities.length} miast`,
    areas.length === 1 ? areaShort(areas[0]) : `${areas.length} obszary`,
  ].join(' · ')

  return (
    <div className="tb">
      {wide
        ? (
          <div className="tb-bar" role="group" aria-label="Co pokazuje tabela">
            <div className="tb-row">{segMeasures}{segCities}</div>
            <div className="tb-row">
              {segAreas}
              <div className="tb-seg tb-end">{swapBtn}{sortLine}{exportEl}</div>
            </div>
          </div>
        )
        : (
          <div className="tb-bar" role="group" aria-label="Co pokazuje tabela">
            <button type="button" className="tb-btn tb-summary" onClick={() => setPicker('bar')} aria-haspopup="dialog">
              <span className="tb-summary-text">{summary}</span><span aria-hidden="true">Zmień ▾</span>
            </button>
            <div className="tb-row tb-row-compact">{sortLine}{exportEl}</div>
          </div>
        )}

      {table_}

      <p className="compare-note tb-note">
        {areaNote}
        {model.moved ? ' Miara, która nie ma w nim wartości, jest pokazana dla najbliższego obszaru; jest to zapisane przy jej nazwie.' : ''}
        {' '}Pogrubiona liczba to najlepsza wartość w wierszu, przygaszona najsłabsza. „–” oznacza brak danych, a nie zero.
        {lack.length > 0 && model.rowCount > 0 ? ` Brak danych o rozkładach jazdy (liczby o transporcie: „–”): ${lack.join(', ')}.` : ''}
        {model.hidden > 0 && model.rowCount > 0 ? ` Pominięto ${model.hidden} ${model.hidden === 1 ? 'miarę' : 'miar'} bez liczb dla tych miast i obszarów.` : ''}
        {' '}<LinkButton onClick={onOpenLimits}>Czego te liczby nie mówią</LinkButton>
      </p>

      {picker === 'bar' && (
        <Modal title="Co pokazuje tabela" onClose={() => setPicker(null)}>
          <div className="tb-bar tb-bar-modal">
            <div className="tb-row">{segMeasures}</div>
            <div className="tb-row">{segCities}</div>
            <div className="tb-row">{segAreas}</div>
            <div className="tb-row">{swapBtn}<button type="button" className="tb-btn tb-primary" onClick={() => setPicker(null)}>Gotowe</button></div>
          </div>
        </Modal>
      )}
      {picker === 'measures' && (
        <MeasurePicker
          index={index} ids={selection.ids} onClose={() => setPicker(null)}
          onChange={(ids) => { patch({ set: SET_OWN, ids }); writeOwn(ids) }}
        />
      )}
      {picker === 'cities' && (
        <CityPicker
          everyCity={everyCity} transport={transport} names={names} value={cities} onClose={() => setPicker(null)}
          onChange={(list) => { if (list.length) patch({ cities: list }) }}
        />
      )}
    </div>
  )
}
