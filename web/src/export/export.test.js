import { describe, expect, it } from 'vitest'
import { BOM, buildCsv, csvCell, csvNumber } from './csv'
import { exportFilename, isoDate, slug } from './filename'
import {
  chartTable, metaFromRows, metricTable, provenanceCells, tableExport, tableGroups,
} from './shape'
import { buildTable, orderedRecords } from '../features/tables/buildTable'
import { selectionOf, shapeOf } from '../features/tables/spec'
import { indexMetrics } from '../metricTable'
import { atLeastTable, pairTable, reachTable, timeTable, valuesTable } from '../features/charts/exportRows'

const row = (agglomeration, metric, domain, value, extra = {}) => ({
  agglomeration, metric, domain, value, unit: '%', label: `L ${metric}`, tier: 'main', source: 'R5', timetable_date: '2026-11-25',
  population_date: '2021-03-31', population_grid: 'ghsl_census_scaled', ...extra,
})

describe('csv', () => {
  it('writes numbers with all their digits and a decimal comma, and a missing value as an empty cell', () => {
    expect(csvNumber(23.8123456)).toBe('23,8123456')
    expect(csvNumber(0)).toBe('0')
    for (const v of [null, undefined, NaN, Infinity, '3']) expect(csvNumber(v)).toBe('')
    expect(csvNumber(1.5, '.')).toBe('1.5')
  })
  it('quotes text with a semicolon, a quote or a line break, leaves the rest', () => {
    expect(csvCell('a;b')).toBe('"a;b"')
    expect(csvCell('say "x"')).toBe('"say ""x"""')
    expect(csvCell('l1\nl2')).toBe('"l1\nl2"')
    expect(csvCell('Łódź, rdzeń')).toBe('Łódź, rdzeń')
    expect(csvCell(null)).toBe('')
    expect(csvCell(true)).toBe('tak')
  })
  it('has the BOM, semicolons, CRLF and a final line break', () => {
    expect(buildCsv([['a', 'b'], ['x;y', 1.5], ['', null]])).toBe(`${BOM}a;b\r\n"x;y";1,5\r\n;\r\n`)
    expect(buildCsv([['a', 1.5]], { sep: ',', decimal: '.', eol: '\n' })).toBe(`${BOM}a,1.5\n`)
  })
})

describe('file names', () => {
  it('are ASCII, hyphenated, in the order of the project and dated', () => {
    expect(slug('Wrocław, rdzeń')).toBe('wroclaw-rdzen')
    expect(slug('Łódź – Śródmieście')).toBe('lodz-srodmiescie')
    expect(exportFilename({ view: 'porównanie', subject: 'Miary', area: 'core', date: '2026-11-25' })).toBe('zwartosc-miast_porownanie_miary_core_2026-11-25.csv')
    expect(exportFilename({ view: 'wykres', subject: 'Zasięg w 30 min', ext: 'png', date: '2026-01-02' })).toBe('zwartosc-miast_wykres_zasieg-w-30-min_2026-01-02.png')
    expect(/^[\x20-\x7e]+$/.test(exportFilename({ view: 'ąę', subject: 'żźć' }))).toBe(true)
    expect(isoDate(new Date(2026, 10, 5))).toBe('2026-11-05')
  })
})

describe('table shapes', () => {
  const id = 'tp_pt_am_30min_ratio_of_means'
  const index = indexMetrics([
    row('a', id, 'core', 30.123456789),
    row('b', id, 'core', 20),
    row('c', id, 'core', null),
    row('a', id, 'fua', 25),
    row('a', 'area', 'core', 100, { unit: 'km²', source: 'GISCO' }),
  ])
  const groups = tableGroups(index)
  expect(groups.length).toBeGreaterThan(0)
  const names = { a: 'Aaa', b: 'Bbb', c: 'Ccc' }
  const build = (cities, areas, swap = false) => buildTable({
    index, selection: selectionOf({ set: 'all' }, index), cities, areas, shape: shapeOf(cities, areas, swap), names, layers: [],
    onShowLayer: () => {}, transport: ['a', 'b', 'c'], everyCity: ['a', 'b', 'c'],
  })
  it('exports a comparison in the order shown, with ids, labels, raw values and provenance', () => {
    const model = build(['a', 'b', 'c'], ['core'])
    const t = tableExport({ records: orderedRecords(model, { key: id, dir: 'asc' }), names, index })
    const head = t[0]
    expect(head.slice(0, 4)).toEqual(['miara_id', 'miara', 'grupa', 'miasto_id'])
    expect(head.slice(-5)).toEqual(['źródło', 'siatka ludności', 'data ludności', 'data rozkładów', 'uwagi'])
    const reach = t.filter((r) => r[0] === id)
    expect(reach.map((r) => r[3])).toEqual(['b', 'a', 'c'])
    expect(reach[1][7]).toBe(30.123456789)
    expect(reach[2][7]).toBeNull()
    expect(reach[0][10]).toBe(1)
    expect(reach[0][9]).toBe('wyżej = lepiej')
    expect(reach[0].slice(-5)).toEqual(['R5', 'GHSL 250 m przeskalowany do spisu 1 km', '2021-03-31', '2026-11-25', ''])
    expect(t.filter((r) => r[0] === 'area').length).toBe(3)   // a cell without a figure is a row with an empty value, as before
    expect(t.every((r) => r.length === head.length)).toBe(true)
  })
  it('orders the columns by a sort, missing last, ties by the original order, and leaves them without one', () => {
    const model = build(['a', 'b', 'c'], ['core'])
    const cols = (sort) => orderedRecords(model, sort).filter((r) => r.id === id).map((r) => r.col)
    expect(cols({ key: id, dir: 'desc' })).toEqual(['a', 'b', 'c'])
    expect(cols({ key: id, dir: 'asc' })).toEqual(['b', 'a', 'c'])
    expect(cols(null)).toEqual(['a', 'b', 'c'])
    expect(cols({ key: 'no_such_row', dir: 'asc' })).toEqual(['a', 'b', 'c'])
  })
  it('exports one city across areas, and several cities across areas with a row per area', () => {
    const c = tableExport({ records: orderedRecords(build(['a'], ['core', 'fua']), null), names, index })
    expect(c.filter((r) => r[0] === id).map((r) => [r[5], r[7]])).toEqual([['core', 30.123456789], ['fua', 25]])
    const sub = orderedRecords(build(['a', 'b'], ['core', 'fua']), null).filter((r) => r.id === id)
    expect(sub.map((r) => [r.rowKey, r.col])).toEqual([[id + '~core', 'a'], [id + '~core', 'b'], [id + '~fua', 'a'], [id + '~fua', 'b']])
    const swapped = orderedRecords(build(['a', 'b'], ['core', 'fua'], true), null).filter((r) => r.id === id)
    expect(swapped.map((r) => [r.rowKey, r.col])).toEqual([[id + '~a', 'core'], [id + '~a', 'fua'], [id + '~b', 'core'], [id + '~b', 'fua']])
    const m = metricTable({ index, id, cityIds: ['a', 'b', 'c'], names, areas: ['core', 'fua'], area: 'core' })
    expect(m[0][9]).toBe('miejsce w obszarze Miasto')
    expect(m.filter((r) => r[4] === 'core').map((r) => [r[2], r[9]])).toEqual([['a', 1], ['b', 2], ['c', '']])
    expect(m.filter((r) => r[4] === 'fua').every((r) => r[9] === '')).toBe(true)
    expect(provenanceCells(null)).toEqual(['', '', '', '', ''])
  })
  it('takes the provenance of a chart from the metrics rows', () => {
    const meta = metaFromRows([row('a', 'm', 'core', 1)])
    expect(meta).toMatchObject({ populationDate: '2021-03-31', timetableDate: '2026-11-25', populationGrid: 'GHSL 250 m przeskalowany do spisu 1 km' })
    const t = chartTable({ title: 'Wykres', area: { id: 'core', label: 'Miasto' } }, { head: ['x'], rows: [[1], [null]] }, meta)
    expect(t[0].slice(0, 4)).toEqual(['wykres', 'obszar_id', 'obszar', 'x'])
    expect(t[1].slice(0, 4)).toEqual(['Wykres', 'core', 'Miasto', 1])
    expect(t[2][3]).toBeNull()
    expect(t[1].slice(-2)).toEqual(['2026-11-25', ''])
  })
})

describe('chart data', () => {
  it('writes the drawn values and leaves gaps empty', () => {
    const a = atLeastTable([{ key: 'a', label: 'Aaa', xs: [0, 50], ys: [100, null] }, { key: 'b', label: 'Bbb', xs: [0, 50], ys: null }])
    expect(a.rows).toEqual([['a', 'Aaa', 0, 100], ['a', 'Aaa', 50, null], ['b', 'Bbb', 0, null], ['b', 'Bbb', 50, null]])
    const r = reachTable([{ key: 'a', label: 'Aaa', xs: [15], rom: [10], p25: [5] }])
    expect(r.rows[0]).toEqual(['a', 'Aaa', 15, 10, null, 5, null, null])
    const v = valuesTable([{ key: 'a', label: 'Aaa', value: 3 }, { key: 'b', label: 'Bbb', value: null }], { median: 3, unit: '%' })
    expect(v.rows).toEqual([['a', 'Aaa', 3, '%'], ['b', 'Bbb', null, '%'], ['mediana', 'mediana', 3, '%']])
    const p = pairTable([{ key: 'a', label: 'Aaa', a: 10, b: 15 }, { key: 'b', label: 'Bbb', a: 1, b: null }], { aLabel: '30', bLabel: '45', unit: '%' })
    expect(p.rows).toEqual([['a', 'Aaa', 10, 15, 5, '%'], ['b', 'Bbb', 1, null, null, '%']])
    const t = timeTable([{ key: 'pt_am', label: 'rano', v30: 1, v45: null }], [{ key: 'pt_am', label: 'rano', v30: 2, v45: 3 }])
    expect(t.rows[1]).toEqual(['mediana siedmiu miast', 'pt_am', 'rano', 2, 3, '%'])
  })
})
