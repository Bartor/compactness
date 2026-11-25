import { Hint } from '@bartor-net/ui-kit'
import TableBuilder from './features/tables/TableBuilder'
import { DEFAULT_TABLE } from './features/tables/spec'

export const COMPARE_TABS = [
  { key: 'miary', label: 'Miary' },
  { key: 'wykresy', label: 'Wykresy' },
]

/**
 * The body of the comparison (no city selected): the configurable table of measures (features/tables: which measures, which
 * cities, which areas; by default the story measures of the seven agglomerations with timetables in the area chosen in the
 * header), and the charts. `layout` is 'tabs' (the wide dock: `tab` says which of "miary" / "wykresy" is shown, the tabs
 * themselves are on the dock's header line) or 'stack' (a phone's modal: both, one under another). `chart` is the per-city
 * class bars, `spread` the distribution charts. `sort`/`setSort` is the sort of the table, {key: row id, dir} or null: a
 * control on a row puts the cities in the order of that row's numbers. `table`/`onTable` is the state of the table.
 */
export default function Compare({
  index, cities, everyCity, names, area, layers, onShowLayer, onPickCity, hot, setHot, onOpenLimits,
  sort = null, setSort, layout = 'stack', tab = 'miary', chart = null, spread = null, onOpenMetric,
  table = DEFAULT_TABLE, onTable = () => {},
}) {
  if (!everyCity.length) return <Hint>Miary pojawią się po przeliczeniu.</Hint>
  const tabs = layout === 'tabs'

  const metrics = (
    <TableBuilder
      index={index} everyCity={everyCity} transport={cities} names={names} globalArea={area}
      table={table} onTable={onTable} layers={layers} onShowLayer={onShowLayer} onOpenMetric={onOpenMetric}
      onPickCity={onPickCity} hot={hot} setHot={setHot} sort={sort} setSort={setSort} wide={tabs} onOpenLimits={onOpenLimits}
    />
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
