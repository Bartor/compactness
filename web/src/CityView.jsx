import { Callout, DataTable, Hint, Notes, RankList, Warn } from '@bartor-net/ui-kit'
import { NO_DATA } from './metrics'
import { centreRows, highlights, timeOfDay } from './metricTable'
import { areaColumns, cityGroups, reachGroups } from './tableModel'

const dep = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1 })

/**
 * What the page says about a selected agglomeration, in two parts: the metrics by area with its rank among the cities
 * with transport data, and the blocks of what sets it apart, the residents by class of the active value layer
 * (`chart`), what is inside it (time of day, centres, busiest stop areas, each only when the data has it) and the
 * notes. `layout` 'columns' puts the table on the left and the blocks on the right, each scrolling by itself (the
 * dock); 'stack' puts the blocks first and the table under them (a phone's sheet). `nodes` is {layer, nodes} from
 * useCityNodes or null.
 */
export default function CityView({
  agglomeration, index, cities, layers, onShowLayer, nodes, onPickNode, chart = null, spread = null, layout = 'stack',
}) {
  const agg = agglomeration.id
  const groups = cityGroups({ index, cities, agg, layers, onShowLayer })
  const stands = highlights(index, cities, agg)
  // the distribution charts (when charts.json is there) carry the time-of-day figures with their own table view,
  // so the plain table is only shown without them
  const day = spread ? null : timeOfDay(index, agg)
  const centres = centreRows(index, agg)
  const columns = layout === 'columns'

  const table = (
    <section className="city-metrics" aria-label={`Miary: ${agglomeration.name}`}>
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
              caption={`Miary: ${agglomeration.name}`} labelHead="Miara" className={columns ? 'city-table dock-table' : 'city-table'}
              columns={areaColumns()} groups={groups}
              resizable={columns ? 'all' : false} density={columns ? 'compact' : 'regular'}
            />
            <Hint>
              „–” oznacza brak danych, a nie zero. Kolumna „Poz.” to miejsce wśród miast z danymi o transporcie.
            </Hint>
          </>
        )}
    </section>
  )

  const blocks = (
    <div className="city-blocks">
      {stands.length > 0 && (
        <Callout title="Co wyróżnia">
          <Notes>{stands.map((s) => <li key={s}>{s}</li>)}</Notes>
        </Callout>
      )}
      {chart && (
        <section>
          <h4>Mieszkańcy w klasach warstwy</h4>
          {chart}
        </section>
      )}
      {spread && <section><h4>Rozkład mieszkańców</h4>{spread}</section>}
      {day && (
        <section>
          <h4>Pora dnia</h4>
          <DataTable
            caption="Zasięg komunikacją o różnych porach" labelHead="Pora dnia" maxHeight="none"
            columns={[{ key: '30', head: '30 min' }, { key: '45', head: '45 min' }]}
            groups={reachGroups(day, 'Zasięg komunikacją, obszar „Miasto”')}
          />
        </section>
      )}
      {centres.length > 0 && (
        <section>
          <h4>Z centrów</h4>
          <DataTable
            caption="Zasięg komunikacją z centrów" labelHead="Z centrów" maxHeight="none"
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
    </div>
  )

  return columns
    ? <div className="city-columns">{table}{blocks}</div>
    : <div className="city-stack">{blocks}<h4>Miary</h4>{table}</div>
}
