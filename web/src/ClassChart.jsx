import { Chips, Donut, HAS_HOVER, Hint, SplitBody, SplitTable } from '@bartor-net/ui-kit'
import { rampLegend } from './ramp'
import { focusOf } from './classFocus'
import { focusPick, pinnedOf } from './classPick'
import {
  SHARE_AREAS, layerAggs, pickedSum, scopeData, scopeLabel, shareFractions, shareText,
} from './classShares'
import StackBars from './kitx/StackBars'

export const NODATA_COLOR = '#8A909C'

const nf = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0, useGrouping: 'always' })

/** "mieszkańcy: Wrocław, cały obszar" and the switch between the whole area and the core city. */
export function ScopeLine({ aggName, area, onArea }) {
  return (
    <div className="scope-line">
      <span>mieszkańcy: {scopeLabel(aggName, area)}</span>
      {onArea && (
        <Chips
          tight items={SHARE_AREAS.map((a) => ({ key: a.key, label: a.label, on: a.key === area }))}
          onPick={onArea}
        />
      )}
    </div>
  )
}

/** The classes of a layer for a chart: [{key, label, color}] in ramp order. */
export const classParts = (layer) => rampLegend(layer.ramp, '').map((r, i) => ({ key: String(i), label: r.label, color: r.color }))

const NO_LAYER = 'Włącz warstwę wartości („Co pokazać”), aby zobaczyć, ilu mieszkańców leży w każdej klasie.'

/**
 * Residents and cells by class of the active value layer for one scope: a ring, a table beside it, and a line that
 * adds up the pinned classes. Pointing at a slice or a row, or clicking it, is the same as doing it in the legend
 * (`focus` is the page's useFocuses value), so the map follows. `doc` is the class-shares file or null.
 */
export function CityClassChart({ layer, doc, aggId, aggName, area, onArea, focus }) {
  if (!layer) return <Hint>{NO_LAYER}</Hint>
  const scope = scopeData(doc, layer.id, aggId, area)
  if (!scope) {
    return <Hint>Dla tej warstwy nie ma liczb mieszkańców w klasach{aggName ? ` dla obszaru: ${aggName}` : ''}.</Hint>
  }
  const parts = classParts(layer)
  const fr = shareFractions(scope)
  const own = focusOf(focus.focuses, layer.id)
  const pick = focusPick(own, layer.id, focus, HAS_HOVER)
  const sum = pickedSum(scope, pinnedOf(own, layer.id))
  const noDataLabel = layer.nodata_label || 'brak danych GTFS'
  const rows = parts.map((p, i) => ({
    ...p, value: scope.pop[i],
    cells: [nf.format(scope.pop[i]), shareText(fr.pop, i) || '0 %', nf.format(scope.cells[i]), shareText(fr.cells, i) || '0 %'],
  }))
  if (scope.nodataPop != null) {
    rows.push({
      key: 'nodata', label: noDataLabel, color: NODATA_COLOR, value: scope.nodataPop,
      cells: [nf.format(scope.nodataPop), shareText([fr.nodataPop], 0) || '0 %', nf.format(scope.nodataCells), shareText([fr.nodataCells], 0) || '0 %'],
    })
  }
  return (
    <div className="class-chart">
      <ScopeLine aggName={aggName} area={area} onArea={onArea} />
      <SplitBody>
        {scope.totalPop > 0 && (
          <Donut rows={rows} pick={pick} label={`Mieszkańcy według klas: ${layer.title}`} />
        )}
        <SplitTable
          columns={[{ label: 'Mieszkańcy', tone: 'strong' }, { label: '% mieszk.' }, { label: 'Komórki' }, { label: '% komórek' }]}
          rows={rows.map((r) => ({ key: r.key, label: r.label, color: r.color, cells: r.cells }))}
          pick={pick}
        />
      </SplitBody>
      <p className="class-sum" aria-live="polite">
        {sum.pop > 0 || sum.cells > 0 || own.pinned?.length
          ? `wybrane klasy: ${shareText([sum.popShare], 0) || '0 %'} mieszkańców, ${shareText([sum.cellShare], 0) || '0 %'} komórek`
          : 'Kliknij klasę, aby zostawić ją na mapie i zobaczyć, jaką część mieszkańców i komórek obejmuje.'}
      </p>
      <p className="class-total">Razem: {nf.format(scope.totalPop)} mieszkańców, {nf.format(scope.totalCells)} komórek 250 m.</p>
    </div>
  )
}

/**
 * One 100 % bar per city: how the residents of each city split into the classes of the active value layer. Same
 * linking as above. `cities` is the order to try (ids), `names` {id: name}; clicking a city's name selects it.
 */
export function CitiesClassBars({ layer, doc, cities, names, area, onArea, focus, onPickCity, hot, onHot, pinned }) {
  if (!layer) return <Hint>{NO_LAYER}</Hint>
  const present = layerAggs(doc, layer.id)
  const order = [...cities.filter((c) => present.includes(c)), ...present.filter((c) => !cities.includes(c))]
  const parts = classParts(layer)
  const rows = order.map((agg) => {
    const scope = scopeData(doc, layer.id, agg, area)
    const fr = shareFractions(scope)
    if (!fr) return null
    // the bar is the residents the layer has a value for (100 %), so that cities compare class by class; the share
    // of residents without data is written at the end of the row instead of taking a segment of a different length
    const known = 1 - (fr.nodataPop || 0)
    const ps = parts.map((p, i) => ({ ...p, share: known > 0 ? fr.pop[i] / known : 0 }))
    const note = fr.nodataPop > 0 ? `bez danych: ${shareText([fr.nodataPop], 0)}` : null
    return { key: agg, label: names[agg] || agg, onPick: () => onPickCity(agg), parts: ps, note }
  }).filter(Boolean)
  if (!rows.length) return <Hint>Dla tej warstwy nie ma jeszcze liczb mieszkańców w klasach.</Hint>
  const own = focusOf(focus.focuses, layer.id)
  const pick = focusPick(own, layer.id, focus, HAS_HOVER)
  return (
    <div className="class-chart cities">
      <ScopeLine aggName={null} area={area} onArea={onArea} />
      <StackBars rows={rows} pick={pick} hot={hot} onHot={onHot} pinned={pinned} label={`Mieszkańcy według klas: ${layer.title}`} />
      <p className="class-sum" aria-live="polite">
        {own.layerId === layer.id && own.pinned.length
          ? 'Wybrane klasy są pokazane na mapie; liczba na końcu paska to ich udział w mieszkańcach objętych danymi.'
          : 'Wskaż klasę na pasku albo w legendzie, aby zobaczyć jej udział w każdym mieście; kliknij, aby zostawić ją na mapie.'}
      </p>
      <Legend parts={parts} />
      {rows.some((r) => r.note) && (
        <Hint>
          Każdy pasek to 100 % mieszkańców, dla których warstwa ma wartość, więc miasta można porównywać klasa po
          klasie. Udział mieszkańców bez danych ({layer.nodata_label || 'brak danych GTFS'}) jest podany na końcu paska.
        </Hint>
      )}
    </div>
  )
}

function Legend({ parts }) {
  return (
    <div className="class-key">
      {parts.map((p) => <span key={p.key}><i style={{ background: p.color }} />{p.label}</span>)}
    </div>
  )
}
