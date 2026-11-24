import { Chips, DataTable, Hint, LinkButton } from '@bartor-net/ui-kit'
import { DOMAIN_INFO } from './metricInfo'
import { AREAS, DENSITY_GROUP_IDS } from './metricTable'
import { cityColumns, compareGroups } from './tableModel'

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
      Miasta według: <b>{row.name || row.label}</b>, {sort.dir === 'desc' ? 'od największej' : 'od najmniejszej'} wartości
      {bestFirst ? ' (najlepsze pierwsze)' : ''}.{' '}
      <LinkButton onClick={onReset}>Domyślna kolejność miast</LinkButton>
    </p>
  )
}

/**
 * The body of "Porównanie miast": which area the numbers refer to, the table of the cities with transport data,
 * a shorter table with all cities, and the reminder that "brak danych" is not zero. Shown in the details slot on a
 * desktop and in a modal on a phone. `hot`/`setHot` is the city whose column (and outline on the map) is lit.
 * `sort`/`setSort` and `sortDensity`/`setSortDensity` are the sorts of the two tables, {key: metric id, dir} or
 * null: a control on a row puts the cities in the order of that row's numbers. They live above, so that they
 * survive a change of area and go into the address.
 */
export default function Compare({
  index, cities, everyCity, names, area, setArea, layers, onShowLayer, onPickCity, hot, setHot, onOpenLimits,
  sort = null, setSort, sortDensity = null, setSortDensity,
}) {
  if (!cities.length) return <Hint>Miary pojawią się po przeliczeniu.</Hint>
  const common = { index, area, names, layers, onShowLayer }
  const transport = compareGroups({ ...common, cities })
  const density = compareGroups({ ...common, cities: everyCity, onlyGroups: DENSITY_GROUP_IDS })
  const info = DOMAIN_INFO[area]
  return (
    <>
      <Chips
        items={AREAS.map((a) => ({ key: a, label: DOMAIN_INFO[a].short, on: a === area }))}
        onPick={setArea}
      />
      <p className="compare-area">{info.read}</p>
      <SortNote groups={transport} sort={sort} onReset={() => setSort?.(null)} />
      <DataTable
        caption="Porównanie miast z danymi o transporcie" className="compare-table" labelHead="Miara"
        columns={cityColumns(cities, names, onPickCity)} groups={transport}
        sortBy="row" sort={sort} onSortChange={setSort}
        hot={hot} onHot={setHot}
      />
      <Hint>
        Pogrubiona liczba to najlepsza wartość w wierszu, przygaszona najsłabsza; nie oznaczamy miar, w których
        „lepiej” nie ma sensu. Strzałki przy mierze ustawiają miasta od najlepszego (jeszcze raz: od najgorszego,
        trzeci raz: jak na początku). Kliknij nazwę miasta, aby zobaczyć jego miary.
      </Hint>

      {density.length > 0 && (
        <>
          <h4>Gęstość: wszystkie {everyCity.length} miast</h4>
          <SortNote groups={density} sort={sortDensity} onReset={() => setSortDensity?.(null)} />
          <DataTable
            caption="Gęstość i forma wszystkich aglomeracji" className="compare-table" labelHead="Miara"
            columns={cityColumns(everyCity, names, onPickCity)} groups={density}
            sortBy="row" sort={sortDensity} onSortChange={setSortDensity}
            hot={hot} onHot={setHot}
          />
        </>
      )}
      <Hint>
        „–” oznacza brak danych, a nie zero: miary nie da się policzyć albo nie dotyczy tego obszaru.{' '}
        <LinkButton onClick={onOpenLimits}>Czego te liczby nie mówią</LinkButton>
      </Hint>
    </>
  )
}
