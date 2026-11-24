import fs from 'node:fs'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { cityColors, classIndexOf, classLink, medianRows, togglePin } from './chartLink'
import { EMPTY_FOCUS, hoverClass, togglePinned } from './classFocus'
import { CityCharts, ComparisonCharts } from './ChartsPanel'
import Compare from './Compare'

describe('chart linking', () => {
  it('gives the selected city the first colour, then pinned ones, three at most, no city twice', () => {
    expect(Object.keys(cityColors('a', ['b', 'a', 'c', 'd']))).toEqual(['a', 'b', 'c'])
    expect(Object.keys(cityColors(null, ['x', 'y']))).toEqual(['x', 'y'])
    expect(cityColors(null, [])).toEqual({})
    const c = cityColors('a', ['b'])
    expect(c.a).not.toBe(c.b)
  })
  it('toggles pins', () => {
    expect(togglePin(['a'], 'b')).toEqual(['a', 'b'])
    expect(togglePin(['a', 'b'], 'a')).toEqual(['b'])
  })
  it('maps the legend class focus to the charts class keys and back', () => {
    const calls = []
    const focus = {
      focuses: { L: hoverClass(togglePinned(EMPTY_FOCUS, 'L', 2), 'L', 1) },
      onHover: (...a) => calls.push(['hover', ...a]), onToggle: (...a) => calls.push(['toggle', ...a]),
    }
    const l = classLink(focus, 'L')
    expect(l.hot).toBe('c1')
    expect(l.pinned).toEqual(['c2'])
    l.onHot('c4'); l.onHot(null); l.onPin('c3'); l.onPin('nonsense')
    expect(calls).toEqual([['hover', 'L', 4], ['hover', 'L', null], ['toggle', 'L', 3]])
    expect(classLink({ ...focus, focuses: {} }, 'L')).toMatchObject({ hot: null, pinned: [] })
    expect(classIndexOf('c12')).toBe(12)
    expect(classIndexOf('x')).toBeNull()
  })
  it('takes the median of the time-of-day rows over cities', () => {
    const row = (v30, v45) => [{ key: 'pt_am', label: 'rano', v30, v45 }]
    expect(medianRows([row(10, 20), row(30, null), row(20, 40)])).toEqual([{ key: 'pt_am', label: 'rano', v30: 20, v45: 30 }])
    expect(medianRows([])).toBeNull()
    expect(medianRows([row(null, null)])[0].v30).toBeNull()
  })
})

const file = 'public/data/charts.json'
describe.skipIf(!fs.existsSync(file))('charts in the dock (real charts.json)', () => {
  const charts = JSON.parse(fs.readFileSync(file, 'utf8'))
  const noop = () => {}
  const link = { hot: 'lodz', setHot: noop, pinned: ['krakow'], onPin: noop }
  const focus = { focuses: {}, onHover: noop, onToggle: noop, onClear: noop }
  const layer = { id: 'transport_performance_30', title: 'TP', ramp: { stops: [10, 20, 30, 40, 50, 60], colors: ['#1', '#2', '#3', '#4', '#5', '#6', '#7'] } }
  it('the comparison grid has the four charts and the pair chooser', () => {
    const s = renderToStaticMarkup(h(ComparisonCharts, { charts, layer, focus, link }))
    for (const t of ['Mieszkańcy poniżej minimalnego zasięgu', 'Odsetek mieszkańców', 'Poniżej progu: szczyt i wieczór', 'Zasięg w zależności od czasu podróży']) {
      expect(s).toContain(t)
    }
    expect(s).toContain('Próg: połowa mediany siedmiu miast')
  })
  it('works without an active layer and with a layer the charts do not know', () => {
    expect(renderToStaticMarkup(h(ComparisonCharts, { charts, layer: null, focus, link }))).toContain('Odsetek mieszkańców')
    expect(renderToStaticMarkup(h(ComparisonCharts, { charts, layer: { id: 'zzz', ramp: { colors: [] } }, focus, link }))).toContain('Odsetek mieszkańców')
  })
  it('the city column has the curve, the reach band, time of day and the dot strip', () => {
    const s = renderToStaticMarkup(h(CityCharts, { charts, layer, focus, link, agg: 'wroclaw' }))
    expect(s).toContain('Pory dnia')
    expect(s).toContain('Zasięg w zależności od czasu podróży')
    expect(s).toContain('Mieszkańcy poniżej minimalnego zasięgu')
  })
  it('the dock tab "Rozkład" exists only when the charts are there', () => {
    const base = {
      index: {}, cities: ['a'], everyCity: ['a'], names: {}, area: 'core', setArea: noop, layers: [], onShowLayer: noop,
      onPickCity: noop, hot: null, setHot: noop, onOpenLimits: noop, layout: 'tabs', tab: 'metrics', setTab: noop,
    }
    expect(renderToStaticMarkup(h(Compare, { ...base, spread: h('i') }))).toContain('Rozkład')
    expect(renderToStaticMarkup(h(Compare, base))).not.toContain('Rozkład')
  })
})
