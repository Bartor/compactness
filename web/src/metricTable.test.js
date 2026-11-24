import { describe, expect, it } from 'vitest'
import {
  AREAS, allCities, areaRow, buildGroups, centreRows, cityCell, highlights, indexMetrics, markExtremes, metricArea,
  metricName, nodeSub, plainText, rankOf, sourceModel, standing, timeOfDay, topNodes, transportCities,
} from './metricTable'
import { shareText, sharesFor } from './classShares'

const row = (agglomeration, metric, domain, value, extra = {}) => ({
  agglomeration, metric, domain, value, unit: '%', label: `L ${metric}`, tier: 'main', ...extra,
})
const flat = (s) => s.replace(/ /g, ' ')

// seven cities with transport data, two without
const seven = ['warszawa', 'krakow', 'wroclaw', 'poznan', 'lodz', 'trojmiasto', 'gzm']
const rows = [
  ...seven.map((c, i) => row(c, 'tp_pt_am_30min', 'core', 20 + i * 2)),          // gzm best, warszawa weakest
  ...seven.map((c, i) => row(c, 'dxs_dense_underserved_share', 'core', 10 + i)),  // lower is better: warszawa best
  ...seven.map((c, i) => row(c, 'area', 'core', 100 + i, { unit: 'km²' })),
  ...['kielce', 'lublin'].map((c) => row(c, 'area', 'core', 90, { unit: 'km²' })),
  ...seven.map((c, i) => row(c, 'tram_speed_median', 'city_tram_network', 15 + i, { unit: 'km/h' })),
  row('lodz', 'tp_pt_am_30min', 'fua', null),
  row('lodz', 'mystery_metric', 'core', 3, { label: 'Tajemnicza miara' }),
  row('lodz', 'qa_only', 'core', 3, { tier: 'qa' }),
]
const index = indexMetrics(rows)

describe('index and cities', () => {
  it('indexes by metric, city and domain and drops qa rows', () => {
    expect(index.tp_pt_am_30min.lodz.core.value).toBe(28)
    expect(index.qa_only).toBeUndefined()
  })
  it('the cities with transport data are those with a metric beyond size and form, in the fixed order', () => {
    expect(transportCities(index, ['kielce', 'lublin'])).toEqual(seven)
    expect(allCities(index, ['kielce', 'lublin'])).toEqual([...seven, 'kielce', 'lublin'])
  })
  it('finds the row of an area; the tram network stands in for any area, but only in the first column of a city table', () => {
    expect(areaRow(index, 'tram_speed_median', 'lodz', 'fua').value).toBe(19)
    expect(areaRow(index, 'tp_pt_am_30min', 'lodz', 'urban_centre')).toBeNull()
    expect(cityCell(index, 'tram_speed_median', 'lodz', 'core').value).toBe(19)
    expect(cityCell(index, 'tram_speed_median', 'lodz', 'fua')).toBeNull()
  })
})

describe('groups', () => {
  it('lists the metrics of the file under the groups of metricInfo and unknown ones last, without time-of-day ids', () => {
    const g = buildGroups({ ...index, tp_pt_midday_30min: index.tp_pt_am_30min })
    expect(g.map((x) => x.id)).toEqual(['size', 'supply', 'match', 'reach', 'other'])
    expect(g.find((x) => x.id === 'other').metrics).toEqual(['mystery_metric'])
    expect(g.find((x) => x.id === 'reach').metrics).toEqual(['tp_pt_am_30min'])
  })
  it('a group with no metric in the data disappears; onlyGroups narrows and drops the leftovers', () => {
    expect(buildGroups(index, { onlyGroups: ['size', 'form'] }).map((x) => x.id)).toEqual(['size'])
  })
  it('names a metric from METRIC_INFO, else from the label of the file, else the id', () => {
    expect(metricName(index, 'area')).toBe('Powierzchnia')
    expect(metricName(index, 'mystery_metric')).toBe('Tajemnicza miara')
    expect(metricName({}, 'zzz')).toBe('zzz')
  })
  it('prints a number without its unit; null for no data', () => {
    expect(flat(plainText({ value: 23.81, unit: '%' }))).toBe('23,8')
    expect(plainText({ value: null, unit: '%' })).toBeNull()
    expect(plainText({ value: 0, unit: '' })).toBe('0')
  })
})

describe('best and weakest', () => {
  it('marks the best and weakest by direction', () => {
    const v = [1, 5, 3, null]
    expect([...markExtremes(v, 'higher').best]).toEqual([1])
    expect([...markExtremes(v, 'higher').worst]).toEqual([0])
    expect([...markExtremes(v, 'lower').best]).toEqual([0])
    expect([...markExtremes(v, 'lower').worst]).toEqual([1])
  })
  it('marks nothing without a direction, with fewer than three values, or when all are equal', () => {
    expect(markExtremes([1, 2, 3], null).best.size).toBe(0)
    expect(markExtremes([1, 2, null], 'higher').best.size).toBe(0)
    expect(markExtremes([2, 2, 2], 'higher').best.size).toBe(0)
  })
  it('ties share the mark', () => {
    expect([...markExtremes([5, 5, 1], 'higher').best]).toEqual([0, 1])
  })
  it('ranks with ties sharing the better place', () => {
    expect(rankOf([10, 20, 20, 5], 20, 'higher')).toBe(1)
    expect(rankOf([10, 20, 20, 5], 10, 'higher')).toBe(3)
    expect(rankOf([10, 20, 5], 5, 'lower')).toBe(1)
    expect(rankOf([10], null, 'higher')).toBeNull()
  })
})

describe('standing and "co wyróżnia"', () => {
  it('falls back to the first area that has the metric', () => {
    expect(metricArea(index, 'tp_pt_am_30min', seven)).toBe('core')
    expect(metricArea(index, 'tram_speed_median', seven)).toBe('city_tram_network')
    expect(metricArea(index, 'nothing', seven)).toBeNull()
    expect(metricArea({ m: { a: { fua: { value: 1 } } } }, 'm', ['a'])).toBe('fua')
    expect(AREAS[0]).toBe('core')
  })
  it('needs three cities with a value and a value for the city', () => {
    expect(standing(index, 'mystery_metric', seven, 'lodz', 'higher')).toBeNull()
    expect(standing(index, 'tp_pt_am_30min', seven, 'kielce', 'higher')).toBeNull()
    const s = standing(index, 'tp_pt_am_30min', seven, 'gzm', 'higher')
    expect(s).toMatchObject({ rank: 1, n: 7, first: true, last: false })
  })
  it('states what is first or last, respecting the direction, skipping metrics without one', () => {
    const g = highlights(index, seven, 'gzm')
    // best in reach and tram speed, and the highest (worst) share of dense areas without service
    expect(g).toHaveLength(3)
    expect(g.map((s) => s.replace(/ \(.*$/, ''))).toEqual([
      'Najwyższa wśród siedmiu miast: Prędkość komunikacyjna tramwajów',
      'Najwyższa wśród siedmiu miast: Gęsta zabudowa bez kursów co 20 min',
      'Najwyższa wśród siedmiu miast: Zasięg komunikacją w 30 min',
    ])
    const w = highlights(index, seven, 'warszawa').map(flat)
    // the lowest share of dense areas without service is the best there; the lowest reach and tram speed the worst
    expect(w).toContain('Najniższa wśród siedmiu miast: Gęsta zabudowa bez kursów co 20 min (10,0 %)')
    expect(w.some((s) => s.startsWith('Najniższa wśród siedmiu miast: Zasięg'))).toBe(true)
    expect(w.every((s) => !s.includes('Powierzchnia'))).toBe(true)
  })
  it('gives at most the asked number and nothing for a city in the middle', () => {
    expect(highlights(index, seven, 'poznan')).toEqual([])
    expect(highlights(index, seven, 'gzm', { max: 1 })).toHaveLength(1)
  })
})

describe('inside the agglomeration', () => {
  it('hides the time-of-day block until a time other than the morning peak arrives', () => {
    expect(timeOfDay(index, 'lodz')).toBeNull()
    const more = indexMetrics([
      ...rows, row('lodz', 'tp_pt_midday_30min', 'core', 18), row('lodz', 'tp_pt_midday_45min', 'core', 30),
      row('lodz', 'tp_pt_am_45min', 'core', 35),
    ])
    const t = timeOfDay(more, 'lodz')
    expect(t.map((r) => [r.key, r.v30, r.v45])).toEqual([['am', 28, 35], ['midday', 18, 30]])
  })
  it('lists centre rows by domain, with the label of the row or the domain id', () => {
    expect(centreRows(index, 'lodz')).toEqual([])
    const more = indexMetrics([
      row('lodz', 'tp_pt_am_30min', 'core', 20, { label: 'ogólny' }),
      row('lodz', 'tp_pt_am_30min', 'hub_1km', 40, { label: 'ogólny' }),
      row('lodz', 'tp_pt_am_45min', 'hub_1km', 60),
      row('lodz', 'tp_pt_am_30min', 'centre_1km_piotrkowska', 33, { label: 'Piotrkowska' }),
    ])
    const c = centreRows(more, 'lodz')
    expect(c.map((r) => [r.domain, r.label, r.v30, r.v45])).toEqual([
      ['hub_1km', 'hub_1km', 40, 60], ['centre_1km_piotrkowska', 'Piotrkowska', 33, null],
    ])
  })
  it('picks the eight busiest nodes of a city', () => {
    const f = (id, agg, dep, p = {}) => ({
      type: 'Feature', geometry: { type: 'Point', coordinates: [1, 2] }, properties: { id, agg, name: id, dep_h: dep, ...p },
    })
    const feats = [
      ...Array.from({ length: 10 }, (_, i) => f(`a${i}`, 'x', i + 1)),
      f('b', 'y', 999), f('nodep', 'x', null),
    ]
    const top = topNodes(feats, 'x')
    expect(top.map((n) => n.id)).toEqual(['a9', 'a8', 'a7', 'a6', 'a5', 'a4', 'a3', 'a2'])
    expect(topNodes(feats, 'zzz')).toEqual([])
    expect(topNodes(undefined, 'x')).toEqual([])
  })
  it('describes a node with the weighted values when present, else the directional walk and morning wait', () => {
    expect(nodeSub({ walk_w: 1.25, wait_w: 3, walk_dir: 9, wait_am: 9 })).toBe('dojście 1,3 min, czekanie 3 min')
    expect(nodeSub({ walk_dir: 0.5, wait_am: 4.4 })).toBe('dojście 0,5 min, czekanie 4,4 min')
    expect(nodeSub({ walk_dir: 0.5 })).toBe('dojście 0,5 min')
    expect(nodeSub({})).toBeNull()
  })
})

describe('source note', () => {
  it('collects source, dates, feed, coverage and flags, naming cities only for flags that differ', () => {
    const r = (flag, share) => row('a', 'm', 'core', 1, {
      source: 'S', timetable_date: '2026-11-25', feed_variant: 'all', coverage_share: share, flag,
    })
    const s = sourceModel(
      [{ key: 'a', row: r('f1', 0.5) }, { key: 'b', row: r('f2', null) }, { key: 'c', row: null }],
      { nameOf: (k) => k.toUpperCase() },
    )
    expect(s.source).toBe('S')
    expect(s.dates).toEqual(['rozkłady: 2026-11-25'])
    expect(s.coverage).toEqual([{ key: 'A', share: 0.5 }])
    expect(s.flags).toEqual([{ text: 'f1', keys: ['A'] }, { text: 'f2', keys: ['B'] }])
    const same = sourceModel([{ key: 'a', row: r('f', 1) }, { key: 'b', row: r('f', 1) }])
    expect(same.flags).toEqual([{ text: 'f', keys: [] }])
  })
  it('is empty when no row exists', () => {
    expect(sourceModel([{ key: 'a', row: null }])).toEqual({ source: null, dates: [], feed: null, coverage: [], flags: [] })
  })
})

describe('class shares', () => {
  it('reads shares of a layer for a city, if any', () => {
    expect(sharesFor({ L: { a: [0.5, 0.5] } }, 'L', 'a')).toEqual([0.5, 0.5])
    expect(sharesFor({}, 'L', 'a')).toBeUndefined()
    expect(sharesFor(undefined, 'L', 'a')).toBeUndefined()
    expect(sharesFor({ L: { a: [] } }, 'L', 'a')).toBeUndefined()
  })
  it('prints whole percentages, "<1 %" for crumbs, nothing without a number', () => {
    expect(shareText([0.234, 0.005, 0.761], 0)).toBe('23 %')
    expect(shareText([0.234, 0.005, 0.761], 1)).toBe('<1 %')
    expect(shareText([0.5], 3)).toBe('')
    expect(shareText(undefined, 0)).toBe('')
    expect(shareText([40, 60], 0)).toBe('40 %')   // already in percent
  })
})
