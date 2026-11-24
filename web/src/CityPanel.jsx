import { Callout, DataTable, DetailsPanel, Hint, Notes, RankList, Warn } from '@bartor-net/ui-kit'
import { ACCENT } from './config'
import { NO_DATA } from './metrics'
import { centreRows, highlights, timeOfDay } from './metricTable'
import { areaColumns, cityGroups, reachGroups } from './tableModel'
import Dock from './kitx/Dock'

const dep = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1 })

/**
 * The panel of a selected agglomeration: what sets it apart, all its metrics by area with its rank among the cities
 * with transport data, then what is inside it (time of day, centres, busiest stop areas, each only when the data has
 * it) and the notes about the agglomeration. `nodes` is {layer, nodes} from useCityNodes or null.
 */
export default function CityPanel({
  agglomeration, index, cities, layers, onShowLayer, onClose, nodes, onPickNode,
}) {
  const agg = agglomeration.id
  const groups = cityGroups({ index, cities, agg, layers, onShowLayer })
  const stands = highlights(index, cities, agg)
  const day = timeOfDay(index, agg)
  const centres = centreRows(index, agg)
  const inside = !!day || centres.length > 0 || !!nodes

  return (
    <Dock>
      <DetailsPanel
        pill={agglomeration.phase != null ? `Etap ${agglomeration.phase}` : undefined}
        title={agglomeration.name} color={ACCENT} onClose={onClose}
      >
        {stands.length > 0 && (
          <Callout title="Co wyróżnia">
            <Notes>{stands.map((s) => <li key={s}>{s}</li>)}</Notes>
          </Callout>
        )}

        <h4>Miary</h4>
        {groups.length === 0
          ? (
            <Hint>
              {Object.keys(index).length === 0
                ? 'Miary pojawią się po przeliczeniu.'
                : 'Dla tej aglomeracji nie ma jeszcze przeliczonych miar.'}
            </Hint>
          )
          : (
            <>
              <DataTable
                caption={`Miary: ${agglomeration.name}`} labelHead="Miara" className="city-table"
                columns={areaColumns()} groups={groups}
              />
              <Hint>
                „–” oznacza brak danych, a nie zero. Kolumna „Poz.” to miejsce wśród miast z danymi o transporcie.
              </Hint>
            </>
          )}

        {inside && <h4 className="city-inside">W środku aglomeracji</h4>}
        {day && (
          <section>
            <DataTable
              caption="Zasięg komunikacją o różnych porach"
              labelHead="Pora dnia"
              columns={[{ key: '30', head: '30 min' }, { key: '45', head: '45 min' }]}
              groups={reachGroups(day, 'Zasięg komunikacją, obszar „Miasto”')}
            />
          </section>
        )}
        {centres.length > 0 && (
          <section>
            <DataTable
              caption="Zasięg komunikacją z centrów"
              labelHead="Z centrów"
              columns={[{ key: '30', head: '30 min' }, { key: '45', head: '45 min' }]}
              groups={reachGroups(centres, 'Zasięg komunikacją w porannym szczycie, promień 1 km od centrum')}
            />
          </section>
        )}
        {nodes && (
          <section>
            <h4>Najruchliwsze zespoły przystanków</h4>
            <RankList
              items={nodes.nodes.map((n) => ({
                key: n.id, title: n.name, sub: n.sub || NO_DATA, value: `${dep.format(n.dep)} odj./h`,
                onPick: () => onPickNode(nodes.layer, n),
              }))}
            />
            <Hint>Kliknij zespół, aby pokazać go na mapie.</Hint>
          </section>
        )}

        {agglomeration.note && <Warn>{agglomeration.note}</Warn>}
      </DetailsPanel>
    </Dock>
  )
}
