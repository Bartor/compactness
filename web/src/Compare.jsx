import { Chips, Hint, LinkButton } from '@bartor-net/ui-kit'
import { DOMAIN_INFO } from './metricInfo'
import { AREAS, DENSITY_GROUP_IDS } from './metricTable'
import { cityColumns, compareGroups } from './tableModel'
import ExpandTable from './kitx/ExpandTable'

/**
 * The body of "Porównanie miast": which area the numbers refer to, the table of the cities with transport data,
 * a shorter table with all cities, and the reminder that "brak danych" is not zero. Shown in the details slot on a
 * desktop and in a modal on a phone. `hot`/`setHot` is the city whose column (and outline on the map) is lit.
 */
export default function Compare({
  index, cities, everyCity, names, area, setArea, layers, onShowLayer, onPickCity, hot, setHot, onOpenLimits,
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
      <ExpandTable
        caption="Porównanie miast z danymi o transporcie"
        columns={cityColumns(cities, names, onPickCity)} groups={transport}
        hot={hot} onHot={setHot}
      />
      <Hint>
        Pogrubiona liczba to najlepsza wartość w wierszu, przygaszona najsłabsza; nie oznaczamy miar, w których
        „lepiej” nie ma sensu. Kliknij nazwę miasta, aby zobaczyć jego miary.
      </Hint>

      {density.length > 0 && (
        <>
          <h4>Gęstość: wszystkie {everyCity.length} miast</h4>
          <ExpandTable
            caption="Gęstość i forma wszystkich aglomeracji"
            columns={cityColumns(everyCity, names, onPickCity)} groups={density}
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
