import { Callout, DataTable, Hint, Notes, RankList, Warn } from '@bartor-net/ui-kit'
import { DOMAIN_INFO } from './metricInfo'
import { NO_DATA } from './metrics'
import { centreRows, headlineRows, highlights, timeOfDay } from './metricTable'
import { cityGroups, reachGroups, valueColumns } from './tableModel'
import { titleCase } from './names'
import { shareText } from './nodePopup'
import NodeDetail from './features/nodes/NodeDetail'
import ExportButtons from './export/ExportButtons'
import SurveyContext from './features/context/SurveyContext'
import { cityTable } from './export/shape'

const dep = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1 })

export const CITY_TABS = [
  { key: 'najwazniejsze', label: 'Najważniejsze' },
  { key: 'miary', label: 'Wszystkie miary' },
  { key: 'wykresy', label: 'Wykresy' },
  { key: 'przesiadki', label: 'Przesiadki' },
  { key: 'predkosci', label: 'Prędkości' },
]

/** What the page says about a selected agglomeration, as the content of one tab of its panel (the tabs are on the dock's header line). */
export default function CityView({
  agglomeration, index, pool, transport, layers, area, tab = 'najwazniejsze', onShowLayer, nodes, onPickNode, chart = null,
  timeChart = null, spread = null, onOpenMetric, hasPoints = true, layout = 'columns', survey = null,
  nodePick = null, detail = null, nodeHot = null, onNodeHot, onNodeClose, nodeOrder = 'dep', onNodeOrder, timetableDate,
  speed = null, speedStatus = 'idle', onSpeedRetry,
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
                resizable={wide ? 'all' : false} widthsKey="compactness-city" density={wide ? 'compact' : 'regular'}
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
  if (tab === 'predkosci') {
    return (
      <div className="city-speed">
        {speed}
        {!speed && speedStatus === 'error' && (
          <Hint>Nie udało się wczytać tabeli linii. <button type="button" className="more-link" onClick={onSpeedRetry}>Spróbuj ponownie</button></Hint>
        )}
        {!speed && speedStatus !== 'error' && <Hint>Wczytywanie tabeli linii…</Hint>}
      </div>
    )
  }
  if (tab === 'przesiadki') {
    const sel = nodePick?.id
    return (
      <div className={`city-stops${sel && wide ? ' with-card' : ''}`}>
        <div className="stops-list">
          {!hasPoints && <Hint>Ta warstwa pojawi się po przeliczeniu.</Hint>}
          {hasPoints && !nodes && <Hint>Dla tej aglomeracji nie ma danych o zespołach przystanków albo wciąż się wczytują.</Hint>}
          {nodes && (
            <>
              <h4>Najruchliwsze zespoły przystanków</h4>
              <div className="stops-order" role="group" aria-label="Kolejność listy">
                <button type="button" aria-pressed={nodeOrder === 'dep'} onClick={() => onNodeOrder?.('dep')}>wg odjazdów</button>
                <button type="button" aria-pressed={nodeOrder === 'use'} onClick={() => onNodeOrder?.('use')}>wg udziału przesiadek</button>
              </div>
              <RankList
                items={nodes.nodes.map((n) => ({
                  key: n.id, title: titleCase(n.name), sub: n.sub || NO_DATA, on: n.id === sel,
                  value: nodeOrder === 'use' && n.use != null ? `${shareText(n.use)} podróży` : `${dep.format(n.dep)} odj./h`,
                  onPick: () => onPickNode(nodes.layer, n),
                }))}
              />
              <Hint>
                Kliknij zespół, aby pokazać go na mapie{wide ? ' i zobaczyć jego składowe' : ''}. Udział przesiadek to część
                podróży z próby tras, które zmieniają się w tym miejscu.
              </Hint>
            </>
          )}
        </div>
        {sel && wide && (
          <div className="node-card">
            <header>
              <b>{nodePick.name}</b>
              <button type="button" className="node-card-close" aria-label="Zamknij kartę zespołu (wróć do listy)" onClick={onNodeClose}>×</button>
            </header>
            <NodeDetail node={detail?.node} status={detail?.status || 'idle'} name={nodePick.name} hot={nodeHot?.move} onHot={onNodeHot} timetableDate={timetableDate} />
          </div>
        )}
      </div>
    )
  }
  // 'najwazniejsze'
  // the survey is context, not a result of this project: it closes the tab
  const context = survey ? <div className="city-survey"><SurveyContext data={survey} agg={agg} /></div> : null
  return wide
    ? <><div className="city-two">{best}{picture}</div>{context}</>
    : <div className="city-stack">{best}{picture}{context}</div>
}
