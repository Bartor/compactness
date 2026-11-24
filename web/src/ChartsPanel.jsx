import { useState } from 'react'
import { Select } from '@bartor-net/ui-kit'
import {
  AtLeastCurve, Dumbbell, DotStrip, ReachCurve, TimeOfDay, atLeastSeries, cityIds, dotStripRows, dumbbellRows,
  floorOf, headwaySeries, layerMarks, reachSeries, timeOfDayRows,
} from './features/charts'
import { cityColors, classLink, medianRows } from './chartLink'
import { DOMAIN_INFO } from './metricInfo'

const PAIR_CHOICES = [
  { value: '30v45', label: 'Zasięg w 30 i w 45 min' },
  { value: 'peak_evening_floor', label: 'Poniżej progu: szczyt i wieczór' },
  { value: 'core_uc', label: 'Miasto i centrum miejskie' },
]

/**
 * The charts file has data for the city (core), the urban centre and the area with timetable data (covered); the whole
 * functional area has none of its own, so it reads as "covered". `moved` says the chart shows another area than asked for.
 */
export function chartDomain(area) {
  if (area === 'core' || area === 'urban_centre' || area === 'covered') return { domain: area, moved: false }
  return { domain: 'covered', moved: true }
}

/** Reach curves have no urban-centre data: they read the city instead. */
const reachDomain = (d) => (d === 'urban_centre' ? 'core' : d)

/** The one quiet line when a chart shows another area than the one chosen. */
export function ChartAreaNote({ area }) {
  const { domain, moved } = chartDomain(area)
  const reach = area === 'urban_centre'
  if (!moved && !reach) return null
  return (
    <p className="chart-area-note">
      {moved
        ? `Wykresy nie mają osobnych danych dla obszaru „${DOMAIN_INFO[area]?.short || area}”: pokazujemy „${DOMAIN_INFO[domain].short}”.`
        : 'Krzywa zasięgu w czasie nie ma danych dla centrum miejskiego: pokazujemy miasto.'}
    </p>
  )
}

/**
 * What the charts need from the page: `link` is {hot, setHot, pinned, onPin}, the city state shared with the tables
 * and the map (hot city = its column and outline are lit; clicking a dot or line pins it, several can be pinned),
 * `layer` the active value layer (its class limits go on the curve and its classes are linked to the legend through
 * `focus`, the page's useFocuses value), `area` the global area.
 */
function useCurve(charts, layer, focus, domain) {
  const marks = layer ? layerMarks(charts, layer.id) : null
  const headway = marks?.series === 'headway'
  const series = headway ? headwaySeries(charts, { domain }) : atLeastSeries(charts, { series: 'pt_am_30', domain })
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

const cityLink = (link) => ({ hotSeries: link.hot, onHotSeries: link.setHot, pinnedSeries: link.pinned, onPinSeries: link.onPin })
const rowLink = (link) => ({ hot: link.hot, onHot: link.setHot, pinned: link.pinned, onPin: link.onPin })

const floorNote = (charts) => {
  const f = floorOf(charts, 30)
  return f == null ? undefined : `Próg: połowa mediany siedmiu miast (${Math.round(f)} %).`
}

/** The distribution charts of the comparison ("Wykresy"): how residents are spread, for the seven cities, in one grid. */
export function ComparisonCharts({ charts, layer, focus, link, area = 'core' }) {
  const [pair, setPair] = useState('30v45')
  const { domain } = chartDomain(area)
  const curve = useCurve(charts, layer, focus, domain)
  const colors = cityColors(null, link.pinned)
  const info = { area: { id: domain, label: DOMAIN_INFO[domain].short } }
  const dumb = dumbbellRows(charts, pair)
  return (
    <>
      <ChartAreaNote area={area} />
      <div className="charts-grid">
        <DotStrip
          {...dotStripRows(charts, { measure: 'below_floor_30', domain })} better="low" exportInfo={info}
          title="Mieszkańcy poniżej minimalnego zasięgu (30 min)" note={floorNote(charts)} {...rowLink(link)}
        />
        <AtLeastCurve {...curve.props} colors={colors} {...cityLink(link)} height={230} exportInfo={info} />
        <div className="charts-pair">
          <Select label="Para wartości" value={pair} options={PAIR_CHOICES} onChange={setPair} />
          <Dumbbell {...dumb} title={dumb.label} {...rowLink(link)} />
        </div>
        <ReachCurve series={reachSeries(charts, { domain: reachDomain(domain) })} colors={colors} {...rowLink(link)} height={230} exportInfo={info} />
      </div>
    </>
  )
}

/**
 * The charts of a city: the city coloured, the other cities grey, in every chart. `parts` says which: 'timeofday' (the
 * first tab) or 'atleast', 'reach', 'dotstrip' (the charts tab, laid out in a grid).
 */
export function CityCharts({ charts, layer, focus, link, agg, area = 'core', parts = ['atleast', 'reach', 'timeofday', 'dotstrip'] }) {
  const { domain } = chartDomain(area)
  const curve = useCurve(charts, layer, focus, domain)
  const colors = cityColors(agg, link.pinned)
  const mine = timeOfDayRows(charts, { agg, domain })
  const median = medianRows(cityIds(charts).map((c) => timeOfDayRows(charts, { agg: c, domain })))
  const info = { area: { id: domain, label: DOMAIN_INFO[domain].short } }
  const has = (p) => parts.includes(p)
  return (
    <div className={parts.length > 1 ? 'charts-grid' : 'charts-city'}>
      {has('atleast') && <AtLeastCurve {...curve.props} colors={colors} {...cityLink(link)} height={240} exportInfo={info} />}
      {has('reach') && <ReachCurve series={reachSeries(charts, { domain: reachDomain(domain) })} focus={agg} colors={colors} {...rowLink(link)} height={240} exportInfo={info} />}
      {has('timeofday') && <TimeOfDay rows={mine} compare={median} height={220} exportInfo={info} />}
      {has('dotstrip') && (
        <DotStrip
          {...dotStripRows(charts, { measure: 'below_floor_30', domain })} better="low" selected={agg} exportInfo={info}
          title="Mieszkańcy poniżej minimalnego zasięgu (30 min)" note={floorNote(charts)} {...rowLink(link)}
        />
      )}
    </div>
  )
}
