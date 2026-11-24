import { Callout, DataTable, Hint, Notes, RankList, Warn } from '@bartor-net/ui-kit'
import { DOMAIN_INFO } from './metricInfo'
import { NO_DATA } from './metrics'
import { centreRows, headlineRows, highlights, timeOfDay } from './metricTable'
import { cityGroups, reachGroups, valueColumns } from './tableModel'
import { titleCase } from './names'
import ExportButtons from './export/ExportButtons'
import { cityTable } from './export/shape'

const dep = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1 })

export const CITY_TABS = [
  { key: 'najwazniejsze', label: 'Najważniejsze' },
  { key: 'miary', label: 'Wszystkie miary' },
  { key: 'wykresy', label: 'Wykresy' },
  { key: 'przesiadki', label: 'Przesiadki' },
]

/** What the page says about a selected agglomeration, as the content of one tab of its panel (the tabs are on the dock's header line). */
export default function CityView({
  agglomeration, index, pool, transport, layers, area, tab = 'najwazniejsze', onShowLayer, nodes, onPickNode, chart = null,
  timeChart = null, spread = null, onOpenMetric, hasPoints = true, layout = 'columns',
}) {
  const agg = agglomeration.id
  const areaName = DOMAIN_INFO[area]?.short || area
  const stands = highlights(index, pool, agg, { area, transport })
  const heads = headlineRows(index, pool, agg, area)
  const day = timeChart ? null : timeOfDay(index, agg)
  const centres = centreRows(index, agg)
  const groups = cityGroups({ index, pool, agg, area, layers, onShowLayer, onOpenMetric })
  const wide = layout === 'columns'

  const best = (
    <div className="city-col">
      {stands.length > 0 && (
        <Callout title="Co wyróżnia">
          <Notes>{stands.map((s) => <li key={s}>{s}</li>)}</Notes>
        </Callout>
      )}
      {heads.length > 0 && (
        <section>
          <h4>Najważniejsze liczby: {areaName}</h4>
          <ul className="headline-list">
            {heads.map((h) => (
              <li key={h.id}>
                <button type="button" className="metric-link" onClick={() => onOpenMetric?.(h.id)} title="Otwórz stronę miary">{h.name}</button>
                <b>{h.text}</b>
                {h.rank && <small>{h.rank.rank}. z {h.rank.n}</small>}
                {h.moved && <small>obszar: {DOMAIN_INFO[h.area]?.short}</small>}
              </li>
            ))}
          </ul>
        </section>
      )}
      {agglomeration.note && <Warn>{agglomeration.note}</Warn>}
    </div>
  )
  const picture = (
    <div className="city-col">
      <section><h4>Mieszkańcy w klasach warstwy na mapie</h4>{chart}</section>
      {timeChart}
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
    </div>
  )

  if (tab === 'miary') {
    return (
      <section className="city-metrics" aria-label={`Miary: ${agglomeration.name}`}>
        {groups.length === 0
          ? <Hint>{Object.keys(index).length === 0 ? 'Miary pojawią się po przeliczeniu.' : 'Dla tej aglomeracji nie ma jeszcze przeliczonych miar.'}</Hint>
          : (
            <>
              <DataTable
                caption={`Miary: ${agglomeration.name}, ${areaName}`} labelHead="Miara" className={wide ? 'city-table dock-table' : 'city-table'}
                columns={valueColumns(area)} groups={groups}
                resizable={wide ? 'all' : false} density={wide ? 'compact' : 'regular'}
                labelWidth={wide ? { min: '19rem', max: '26rem' } : undefined}
                toolbar={(
                  <ExportButtons
                    table={() => cityTable({
                      index, agg, name: agglomeration.name,
                      groups: groups.map((g) => ({ id: g.id, title: g.title, metrics: g.rows.map((r) => r.id) })),
                    })}
                    name={{ view: 'miasto', subject: agglomeration.name }}
                  />
                )}
              />
              <p className="compare-note">
                Liczby dotyczą obszaru „{areaName}” (przełącznik u góry strony); inne obszary są na stronie miary. „–” oznacza brak
                danych, a nie zero. Kolumna „Poz.” to miejsce wśród aglomeracji, które mają tę miarę.
              </p>
            </>
          )}
      </section>
    )
  }
  if (tab === 'wykresy') {
    return <div className="city-charts">{spread || <Hint>Wykresy rozkładu pojawią się po przeliczeniu.</Hint>}</div>
  }
  if (tab === 'przesiadki') {
    return (
      <div className="city-stops">
        {!hasPoints && <Hint>Ta warstwa pojawi się po przeliczeniu.</Hint>}
        {hasPoints && !nodes && <Hint>Dla tej aglomeracji nie ma danych o zespołach przystanków albo wciąż się wczytują.</Hint>}
        {nodes && (
          <>
            <h4>Najruchliwsze zespoły przystanków</h4>
            <RankList
              items={nodes.nodes.map((n) => ({
                key: n.id, title: titleCase(n.name), sub: n.sub || NO_DATA, value: `${dep.format(n.dep)} odj./h`,
                onPick: () => onPickNode(nodes.layer, n),
              }))}
            />
            <Hint>Kliknij zespół, aby pokazać go na mapie i otworzyć jego składowe.</Hint>
          </>
        )}
      </div>
    )
  }
  // 'najwazniejsze'
  return wide ? <div className="city-two">{best}{picture}</div> : <div className="city-stack">{best}{picture}</div>
}
