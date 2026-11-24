import { useState } from 'react'
import { Chips } from '@bartor-net/ui-kit'
import {
  AtLeastCurve, Dumbbell, DotStrip, ReachCurve, TimeOfDay, atLeastSeries, cityIds, dotStripRows, dumbbellRows,
  floorOf, headwaySeries, layerMarks, reachSeries, timeOfDayRows,
} from './features/charts'
import { cityColors, classLink, medianRows } from './chartLink'

const PAIR_CHOICES = [
  { key: '30v45', label: '30 i 45 min' },
  { key: 'peak_evening_floor', label: 'Poniżej progu: szczyt i wieczór' },
  { key: 'core_uc', label: 'Rdzeń i centrum miejskie' },
]

/**
 * What the charts need from the page: `link` is {hot, setHot, pinned, onPin}, the city state shared with the tables
 * and the map (hot city = its column and outline are lit; clicking a dot or line pins it, several can be pinned),
 * `layer` the active value layer (its class limits go on the curve and its classes are linked to the legend through
 * `focus`, the page's useFocuses value).
 */
function useCurve(charts, layer, focus) {
  const marks = layer ? layerMarks(charts, layer.id) : null
  const headway = marks?.series === 'headway'
  const series = headway ? headwaySeries(charts) : atLeastSeries(charts, { series: 'pt_am_30' })
  const classes = marks && layer ? classLink(focus, layer.id) : null
  return {
    series,
    props: {
      series, unit: headway ? 'min' : '%', what: headway ? 'kursy' : '',
      title: headway ? 'Odsetek mieszkańców z kursami co najwyżej co N min' : 'Odsetek mieszkańców z zasięgiem co najmniej X (30 min)',
      xLabel: headway ? 'odstęp między kursami, min' : 'zasięg komunikacją + pieszo w 30 min, % ludności z okolicy',
      marks: marks?.stops, markColors: marks && layer ? layer.ramp?.colors : undefined,
      floor: !headway ? floorOf(charts, 30) ?? undefined : undefined,
      ...(classes ? { hot: classes.hot, pinned: classes.pinned, onHot: classes.onHot, onPin: classes.onPin } : {}),
    },
  }
}

function cityLink(link) {
  return {
    hotSeries: link.hot, onHotSeries: link.setHot, pinnedSeries: link.pinned, onPinSeries: link.onPin,
  }
}
function rowLink(link) {
  return { hot: link.hot, onHot: link.setHot, pinned: link.pinned, onPin: link.onPin }
}

const floorNote = (charts) => {
  const f = floorOf(charts, 30)
  return f == null ? undefined : `Próg: połowa mediany siedmiu miast (${Math.round(f)} %).`
}

/** The tab "Rozkład" of the comparison: how residents are spread, for the seven cities, in one grid. */
export function ComparisonCharts({ charts, layer, focus, link }) {
  const [pair, setPair] = useState('30v45')
  const curve = useCurve(charts, layer, focus)
  const colors = cityColors(null, link.pinned)
  return (
    <div className="charts-grid">
      <DotStrip
        {...dotStripRows(charts, { measure: 'below_floor_30' })} better="low"
        title="Mieszkańcy poniżej minimalnego zasięgu (30 min)" note={floorNote(charts)} {...rowLink(link)}
      />
      <AtLeastCurve {...curve.props} colors={colors} {...cityLink(link)} height={230} />
      <div className="charts-pair">
        <Chips tight items={PAIR_CHOICES.map((p) => ({ key: p.key, label: p.label, on: p.key === pair }))} onPick={setPair} />
        <Dumbbell {...dumbbellRows(charts, pair)} title={dumbbellRows(charts, pair).label} {...rowLink(link)} />
      </div>
      <ReachCurve series={reachSeries(charts)} colors={colors} {...rowLink(link)} height={230} />
    </div>
  )
}

/** The charts in the right column of a city: the city coloured, the other cities grey, in every chart. */
export function CityCharts({ charts, layer, focus, link, agg }) {
  const curve = useCurve(charts, layer, focus)
  const colors = cityColors(agg, link.pinned)
  const mine = timeOfDayRows(charts, { agg })
  const median = medianRows(cityIds(charts).map((c) => timeOfDayRows(charts, { agg: c })))
  return (
    <div className="charts-city">
      <AtLeastCurve {...curve.props} colors={colors} {...cityLink(link)} height={210} />
      <ReachCurve series={reachSeries(charts)} focus={agg} colors={colors} {...rowLink(link)} height={210} />
      <TimeOfDay rows={mine} compare={median} height={200} />
      <DotStrip
        {...dotStripRows(charts, { measure: 'below_floor_30' })} better="low" selected={agg}
        title="Mieszkańcy poniżej minimalnego zasięgu (30 min)" note={floorNote(charts)} {...rowLink(link)}
      />
    </div>
  )
}
