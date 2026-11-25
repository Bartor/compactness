import { DataTable, Hint, LinkButton } from '@bartor-net/ui-kit'
import { DOMAIN_INFO } from './metricInfo'
import { cityColumns, compareGroups } from './tableModel'
import ExportButtons from './export/ExportButtons'
import { comparisonTable } from './export/shape'

export const COMPARE_TABS = [
  { key: 'miary', label: 'Miary' },
  { key: 'wykresy', label: 'Wykresy' },
]

/** The groups a table shows, as export wants them: [{id, title, metrics: [ids]}] in the displayed order. */
const shown = (groups) => groups.map((g) => ({ id: g.id, title: g.title, metrics: g.rows.map((r) => r.id) }))

/**
 * The line over a sorted comparison: which metric orders the cities and which way, and the way back to the default
 * order. Nothing when there is no sort or its metric is not in this table (an old link, say).
 */
function SortNote({ groups, sort, onReset }) {
  const row = sort && groups.flatMap((g) => g.rows).find((r) => r.id === sort.key)
  if (!row) return null
  const bestFirst = row.better && sort.dir === (row.better === 'lower' ? 'asc' : 'desc')
  return (
    <p className="compare-sort">
      Aglomeracje według: <b>{row.name || row.label}</b>, {sort.dir === 'desc' ? 'od największej' : 'od najmniejszej'} wartości
      {bestFirst ? ' (najlepsze pierwsze)' : ''}.{' '}
      <LinkButton onClick={onReset}>Domyślna kolejność</LinkButton>
    </p>
  )
}

/**
 * The body of the comparison (no city selected): ONE table of all agglomerations in the area chosen in the header (the
 * seven with timetables first, a divider, then the six with density only), and the charts. `layout` is 'tabs' (the wide
 * dock: `tab` says which of "miary" / "wykresy" is shown, the tabs themselves are on the dock's header line) or 'stack' (a
 * phone's modal: both, one under another). `chart` is the per-city class bars, `spread` the distribution charts.
 * `sort`/`setSort` is the sort of the table, {key: metric id, dir} or null: a control on a row puts the cities in the
 * order of that row's numbers (and drops the grouping, which a mixed order cannot keep).
 */
export default function Compare({
  index, cities, everyCity, names, area, layers, onShowLayer, onPickCity, hot, setHot, onOpenLimits,
  sort = null, setSort, layout = 'stack', tab = 'miary', chart = null, spread = null, onOpenMetric,
}) {
  if (!everyCity.length) return <Hint>Miary pojawią się po przeliczeniu.</Hint>
  const tabs = layout === 'tabs'
  const transport = everyCity.filter((c) => cities.includes(c))
  const rest = everyCity.filter((c) => !cities.includes(c))
  const grouped = !sort?.key && transport.length > 0 && rest.length > 0
  const groups = compareGroups({
    index, cities: everyCity, area, names, layers, onShowLayer, onOpenMetric,
    gapAfter: grouped ? rest[0] : null, noTimetable: rest,
  })
  const columns = cityColumns(everyCity, names, onPickCity, grouped ? { transport, rest } : null)
  const moved = groups.some((g) => g.rows.some((r) => r.movedTo))
  const areaName = DOMAIN_INFO[area]?.short || area

  const metrics = (
    <>
      <SortNote groups={groups} sort={sort} onReset={() => setSort?.(null)} />
      <DataTable
        caption={`Porównanie ${everyCity.length} aglomeracji: ${areaName}`} className={tabs ? 'compare-table dock-table' : 'compare-table'} labelHead="Miara"
        columns={columns} groups={groups}
        sortBy="row" sort={sort} onSortChange={setSort}
        hot={hot} onHot={setHot}
        resizable={tabs ? 'all' : false} widthsKey="compactness-compare" density={tabs ? 'compact' : 'regular'}
        labelWidth={tabs ? { min: '19rem', max: '26rem' } : { min: '11.5rem', max: '12rem' }}
        toolbar={(
          <ExportButtons
            table={() => comparisonTable({ index, cities: everyCity, area, names, groups: shown(groups), sort })}
            name={{ view: 'porownanie', subject: 'miary', area }}
          />
        )}
      />
      <p className="compare-note">
        Liczby dotyczą obszaru „{areaName}” (przełącznik u góry strony).
        {moved ? ' Miara, która nie ma w nim wartości, jest pokazana dla najbliższego obszaru; jest to zapisane przy jej nazwie.' : ''}
        {' '}Pogrubiona liczba to najlepsza wartość w wierszu, przygaszona najsłabsza. „–” oznacza brak danych, a nie zero.{' '}
        <LinkButton onClick={onOpenLimits}>Czego te liczby nie mówią</LinkButton>
      </p>
    </>
  )
  const charts = (
    <div className="compare-charts">
      {spread}
      {chart && <section><h3 className="compare-h3">Mieszkańcy według klas warstwy na mapie</h3>{chart}</section>}
    </div>
  )

  return tabs
    ? <div className="compare-body">{tab === 'wykresy' ? charts : metrics}</div>
    : <div className="compare-body">{metrics}{(spread || chart) && <><h4>Wykresy</h4>{charts}</>}</div>
}
