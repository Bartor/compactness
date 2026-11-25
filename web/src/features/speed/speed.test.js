import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import {
  BANDS, CLASS_BREAKS, CLASS_COLORS, CLASS_LABELS, RAMP, classOf, featureHasLine, featureLineKeys, linesOf, props,
  roundingInterval,
} from './speedModel'
import {
  BASE_OPACITY, DIM_OPACITY, MINZOOM, NONE, QUIET_DELAY, colorExpression, hitTest, idsFilter, lineLayerIds, lineSpecs,
  linesFilter, offsetExpression, opacityExpression, tierFilter,
} from './lineLayers'
import { FASTER_TEXT, NO_DATA, bandBars, renderStretchPopup, speedText, stretchPopupModel, tafText } from './stretchPopup'
import {
  cellValue, compareLines, defaultOrder, filterRows, hotRowKeys, normaliseFilters, parseLines, rowIdFromTarget,
  setFilter, togglePin,
} from './lineTable'
import { clearSpeedCache, layerUrl, loadSpeedLines, resolvedLayer } from './loader'
import SpeedTable from './SpeedTable'
import SpeedLegend, { strongClasses, widthKey } from './SpeedLegend'

const trams = { id: 'speed_tram', kind: 'lines', type: 'geojson', url: 'data/speed/trams.geojson', mode_group: 'tram' }
const buses = { id: 'speed_bus', kind: 'lines', type: 'geojson', url_template: 'data/speed/bus_{agg}.geojson', mode_group: 'bus', cities: ['krakow'] }
const rail = { id: 'speed_rail', kind: 'lines', type: 'geojson', url: 'data/speed/rail.geojson', mode_group: 'rail' }

const tram = {
  id: 'KRK-1a2b3c4d-A', dir: 'A', agg: 'krakow', m: 'tram', name: 'Filharmonia → Stradom', ln: ',1,3,12,', fd: 'krakow_tram',
  len: 1639, ns: 5, stops: 'Filharmonia > Wawel > Stradom', v_w_am: 14.2, t_w_am: 30, a_w_am: 99, al_w_am: 60, ah_w_am: 140,
  v_w_ev: 14.3, t_w_ev: 12, fm_w_ev: 1, v_s_d: 15.1, c: '1111111111111', st: 0.47, x: 14, xs: 0, xp: 5, sw: 8, short: 1,
}

describe('speed classes', () => {
  it('are fixed and city-independent, with brighter colours for faster classes', () => {
    expect(CLASS_BREAKS).toEqual([12, 15, 18, 22, 26])
    expect(CLASS_LABELS).toHaveLength(6)
    expect(CLASS_COLORS).toHaveLength(6)
    const lum = (c) => { const n = parseInt(c.slice(1), 16); return 0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255) }
    for (let i = 1; i < CLASS_COLORS.length; i++) expect(lum(CLASS_COLORS[i])).toBeGreaterThan(lum(CLASS_COLORS[i - 1]))
    expect(RAMP.colors.length).toBe(RAMP.stops.length + 1)
  })
  it('puts a value on a break in the upper class and no value in none', () => {
    expect(classOf(11.99)).toBe(0)
    expect(classOf(12)).toBe(1)
    expect(classOf(17.9)).toBe(2)
    expect(classOf(26)).toBe(5)
    expect(classOf(null)).toBe(-1)
    expect(classOf(undefined)).toBe(-1)
  })
  it('has 13 bands with Wednesday first', () => {
    expect(BANDS).toHaveLength(13)
    expect(BANDS[2].key).toBe('w_am')
    expect(props('w_am')).toMatchObject({ v: 'v_w_am', t: 't_w_am', a: 'a_w_am' })
  })
})

describe('rounding interval', () => {
  it('is length over time plus and minus a minute', () => {
    const r = roundingInterval(2000, 20)      // 6 minutes
    expect(r.minutes).toBeCloseTo(6)
    expect(r.lo).toBeCloseTo(2 / (7 / 60))
    expect(r.hi).toBeCloseTo(2 / (5 / 60))
  })
  it('has no upper bound at a minute or less, and nothing without data', () => {
    expect(roundingInterval(300, 18).hi).toBeNull()
    expect(roundingInterval(null, 18)).toBeNull()
    expect(roundingInterval(1000, 0)).toBeNull()
  })
})

describe('line keys', () => {
  it('reads comma-fenced lines and feeds', () => {
    expect(linesOf(',1,3,12,')).toEqual(['1', '3', '12'])
    expect(featureLineKeys(tram)).toEqual(['krakow|krakow_tram|1', 'krakow|krakow_tram|12', 'krakow|krakow_tram|3'])
    expect(featureHasLine(tram, 'krakow|krakow_tram|3')).toBe(true)
    expect(featureHasLine(tram, 'krakow|krakow_tram|13')).toBe(false)
    expect(featureHasLine(tram, 'wroclaw|krakow_tram|3')).toBe(false)
  })
})

describe('line layer specs', () => {
  it('draws trams from the city-fit zoom, buses later, quiet stretches later still, the highlight on top', () => {
    const s = lineSpecs(trams, 'w_am')
    expect(s.map((x) => x.type)).toEqual(['line', 'line', 'line', 'line', 'line', 'line'])
    expect(s[s.length - 1].id).toBe('speed_tram:hot')
    // the selection casing (features/segments) sits under the hover highlight, off until something is selected
    expect(s[s.length - 2].id).toBe('speed_tram:sel')
    expect(s[s.length - 2].filter).toEqual(NONE)
    expect(s.find((x) => x.id === 'speed_tram:busy:solid').minzoom).toBe(MINZOOM.tram)
    expect(s.find((x) => x.id === 'speed_tram:quiet:solid').minzoom).toBe(MINZOOM.tram + QUIET_DELAY)
    expect(lineSpecs(buses)[0].minzoom).toBe(MINZOOM.bus + QUIET_DELAY)
    expect(s[s.length - 1].filter).toEqual(NONE)
  })
  it('colours by the selected band on the fixed breaks', () => {
    const e = colorExpression('s_d')
    expect(e[1]).toEqual(['get', 'v_s_d'])
    expect(e.filter((x) => typeof x === 'number')).toEqual(CLASS_BREAKS)
  })
  it('draws only stretches with a speed in the band, dashed when flagged', () => {
    const f = tierFilter('w_am', 'busy', true)
    expect(JSON.stringify(f)).toContain('"v_w_am"')
    expect(JSON.stringify(f)).toContain('"short"')
    expect(JSON.stringify(tierFilter('w_am', 'busy', false))).toContain('["!",["any"')
    expect(lineSpecs(trams).find((x) => x.id.endsWith(':dash')).paint['line-dasharray']).toBeTruthy()
  })
  it('offsets directions but not rail lines', () => {
    expect(offsetExpression('w_am', 'rail')).toBe(0)
    expect(offsetExpression('w_am', 'tram')[0]).toBe('interpolate')
    expect(lineSpecs(rail)[0].paint['line-offset']).toBe(0)
  })
  it('fades by class or by matched lines, and not at all without a focus', () => {
    expect(opacityExpression('w_am')).toBe(BASE_OPACITY)
    const byClass = opacityExpression('w_am', { classes: new Set([0]) })
    expect(byClass[0]).toBe('case')
    expect(byClass.slice(-2)).toEqual([BASE_OPACITY, DIM_OPACITY])
    const both = opacityExpression('w_am', { classes: new Set([1]), match: linesFilter(['krakow|krakow_tram|3']) })
    expect(both[1][0]).toBe('any')
  })
  it('builds line and id filters, and none for an empty set', () => {
    expect(linesFilter([])).toEqual(NONE)
    const f = linesFilter(['krakow|krakow_tram|3', 'krakow|krakow_tram|3'])
    expect(f).toHaveLength(2)
    expect(JSON.stringify(f)).toContain('",3,"')
    expect(idsFilter(['b', 'a'])).toEqual(['in', ['get', 'id'], ['literal', ['a', 'b']]])
    expect(idsFilter(null)).toEqual(NONE)
  })
  it('hit-tests the topmost feature of its own layers', () => {
    const hit = hitTest(trams, [{ layer: { id: 'other' }, properties: {} }, { layer: { id: 'speed_tram:busy:solid' }, properties: tram }], 'w_am')
    expect(hit.id).toBe(tram.id)
    expect(hit.cls).toBe(1)
    expect(hit.keys).toContain('krakow|krakow_tram|12')
    expect(hitTest(trams, [], 'w_am')).toBeNull()
    expect(lineLayerIds(trams)).toHaveLength(4)
  })
})

describe('stretch popup', () => {
  it('gives speed with the rounding interval and time above free running with its range', () => {
    expect(speedText(1639, 14.2)).toMatch(/^14,2 km\/h \(±1 min: 12,\d–16,\d\)$/)
    expect(speedText(1639, null)).toBe(NO_DATA)
    expect(tafText(tram, 'w_am')).toBe('99 s/km (60–140)')
    expect(tafText(tram, 'w_ev')).toBe('rozkład szybszy niż model')
    expect(tafText(tram, 'w_md')).toBe(NO_DATA)
  })
  it('says scheduled, not measured, flags short stretches and explains faster-than-model', () => {
    const m = stretchPopupModel(tram, 'w_ev', { weekday: '2026-11-25', saturday: '2026-11-28' })
    expect(m.footer).toContain('rozkład, nie pomiar')
    expect(m.notes).toContain(FASTER_TEXT)
    expect(m.notes.join(' ')).toContain('krótszy niż 5 minut')
    expect(m.subtitle).toBe('tramwaj · linie: 1, 3, 12')
    const os = m.sections.find((s) => s.title === 'Tor (OSM)')
    expect(os.rows[0][1]).toBe('47 %')
  })
  it('has bars for the 11 bands, missing ones empty, no model section for buses', () => {
    const bars = bandBars(tram)
    expect(bars).toHaveLength(11)
    expect(bars.find((b) => b.key === 'w_md').value).toBeNull()
    expect(Math.max(...bars.map((b) => b.width))).toBe(1)
    const bus = stretchPopupModel({ ...tram, m: 'bus', st: undefined }, 'w_am')
    expect(bus.sections.map((s) => s.title)).toEqual(['W wybranym paśmie'])
  })
  it('renders text nodes only', () => {
    const fake = {
      createElement: (tag) => ({ tag, children: [], style: {}, attrs: {}, appendChild(c) { this.children.push(c) },
        setAttribute(k, v) { this.attrs[k] = v } }),
    }
    const root = renderStretchPopup(stretchPopupModel({ ...tram, name: '<b>x</b>' }, 'w_am'), fake)
    expect(root.children[0].textContent).toBe('<b>x</b>')
    expect(root.children.some((c) => c.className === 'sp-bars')).toBe(true)
  })
})

const json = {
  columns: ['key', 'agg', 'mode', 'feed', 'line', 'term', 'official', 'v', 'n', 'hw', 'gap', 'sp', 'flags'],
  timetable_dates: { weekday: '2026-11-25', saturday: '2026-11-28' },
  rows: [
    ['krakow|krakow_tram|10', 'krakow', 'tram', 'krakow_tram', '10', 'A – B', true, Array(13).fill(18), Array(13).fill(5), Array(13).fill(10), 0.4, 520, null],
    ['krakow|krakow_tram|2', 'krakow', 'tram', 'krakow_tram', '2', 'C – D', true, [null, null, 12, ...Array(10).fill(13)], [0, 0, 4, ...Array(10).fill(3)], Array(13).fill(12), null, 450, null],
    ['krakow|krakow_bus|105', 'krakow', 'bus', 'krakow_bus', '105', 'E – F', true, Array(13).fill(25), Array(13).fill(2), Array(13).fill(30), 1, 700, 'feed nieoficjalny, niezweryfikowany'],
    ['wroclaw|wroclaw|33', 'wroclaw', 'tram', 'wroclaw', '33', 'G – H', true, Array(13).fill(16), [0, 0, 0, ...Array(10).fill(1)], Array(13).fill(60), null, 400, null],
  ],
}

describe('line table logic', () => {
  const data = parseLines(json)
  it('parses the columnar file', () => {
    expect(data.rows).toHaveLength(4)
    expect(data.rows[0].line).toBe('10')
    expect(parseLines(null).rows).toEqual([])
  })
  it('keeps only lines that run in the band, of the mode and city', () => {
    const f = { city: 'krakow', mode: 'tram', day: 'weekday', band: 'w_am' }
    expect(filterRows(data.rows, f).map((r) => r.line)).toEqual(['10', '2'])
    expect(filterRows(data.rows, { ...f, band: 'w_n' }).map((r) => r.line)).toEqual(['10'])
    expect(filterRows(data.rows, { ...f, city: null }).map((r) => r.line)).toEqual(['10', '2'])
    expect(filterRows(data.rows, { ...f, mode: 'bus' }).map((r) => r.line)).toEqual(['105'])
  })
  it('keeps the band inside the day type and maps it when the day changes', () => {
    expect(normaliseFilters({ day: 'saturday', band: 'w_am' }).band).toBe('s_d')
    expect(setFilter({ day: 'weekday', band: 'w_ev' }, 'day', 'saturday').band).toBe('s_ev')
    expect(setFilter({ day: 'weekday', band: 'w_ev' }, 'mode', 'nonsense').mode).toBe('tram')
  })
  it('sorts line names naturally and keeps a stable default order', () => {
    expect(['10', '2', 'N1', '1A'].sort(compareLines)).toEqual(['1A', '2', '10', 'N1'])
    expect(defaultOrder(data.rows).map((r) => r.line)).toEqual(['2', '10', '105', '33'])
  })
  it('reads cells for the band, null when missing', () => {
    expect(cellValue(data.rows[1], 'v', 'w_am')).toBe(12)
    expect(cellValue(data.rows[1], 'v', 'w_n')).toBeNull()
    expect(cellValue(data.rows[1], 'cls', 'w_am')).toBe(1)
    expect(cellValue(data.rows[1], 'gap', 'w_am')).toBeNull()
  })
  it('links both ways', () => {
    expect([...hotRowKeys(data.rows, ['krakow|krakow_tram|2', 'nope'])]).toEqual(['krakow|krakow_tram|2'])
    expect(togglePin(['b'], 'a')).toEqual(['a', 'b'])
    expect(togglePin(['a', 'b'], 'a')).toEqual(['b'])
    const tag = { getAttribute: () => 'krakow|krakow_tram|2' }
    const target = { closest: (s) => (s === 'tr' ? { querySelector: () => tag } : null) }
    expect(rowIdFromTarget(target)).toBe('krakow|krakow_tram|2')
    expect(rowIdFromTarget(null)).toBeNull()
  })
})

describe('loader', () => {
  it('resolves per-city bus files and refuses without a city', () => {
    expect(layerUrl(trams, null)).toBe('data/speed/trams.geojson')
    expect(layerUrl(buses, 'krakow')).toBe('data/speed/bus_krakow.geojson')
    expect(layerUrl(buses, null)).toBeNull()
    expect(layerUrl(buses, 'lodz')).toBeNull()
    expect(resolvedLayer(buses, 'krakow').url).toBe('data/speed/bus_krakow.geojson')
  })
  it('fetches once and parses', async () => {
    clearSpeedCache()
    let calls = 0
    const f = () => { calls++; return Promise.resolve({ ok: true, json: () => Promise.resolve(json) }) }
    const a = await loadSpeedLines((u) => `/x/${u}`, f)
    const b = await loadSpeedLines((u) => `/x/${u}`, f)
    expect(a.rows).toHaveLength(4)
    expect(b).toBe(a)
    expect(calls).toBe(1)
  })
  it('rejects with a Polish message and does not cache a failure', async () => {
    clearSpeedCache()
    const bad = () => Promise.resolve({ ok: false, status: 404 })
    await expect(loadSpeedLines((u) => u, bad)).rejects.toThrow('Nie udało się wczytać')
    const good = () => Promise.resolve({ ok: true, json: () => Promise.resolve(json) })
    await expect(loadSpeedLines((u) => u, good)).resolves.toBeTruthy()
  })
})

describe('components', () => {
  const html = (el) => renderToStaticMarkup(el)
  it('renders the table with filters, the selected band and pinned rows', () => {
    const s = html(h(SpeedTable, {
      data: parseLines(json), cityNames: { krakow: 'Kraków', wroclaw: 'Wrocław' },
      filters: { city: 'krakow', mode: 'tram', day: 'weekday', band: 'w_am' }, pinned: ['krakow|krakow_tram|2'],
      hot: ['krakow|krakow_tram|10'],
    }))
    expect(s).toContain('szczyt poranny 07–09')
    expect(s).toContain('data-row-id="krakow|krakow_tram|2"')
    expect(s).toContain('aria-pressed="true"')
    expect(s).toContain('speed-line hot')
    expect(s).toContain('rozkład, nie pomiar')
    expect(s).not.toContain('105')
  })
  it('renders the legend with six classes, widths and the band', () => {
    const s = html(h(SpeedLegend, { layer: trams, band: 's_d', focus: { layerId: 'speed_tram', hover: null, from: null, pinned: [2] } }))
    for (const l of CLASS_LABELS) expect(s).toContain(l)
    expect(s).toContain('sobota, dzień 09–18')
    expect(s).toContain('Pokaż wszystkie klasy')
    expect(widthKey()).toHaveLength(5)
    expect([...strongClasses({ layerId: 'speed_tram', hover: 1, from: 'legend', pinned: [3] }, 'speed_tram')].sort()).toEqual([1, 3])
    expect(strongClasses({ layerId: 'x', hover: 1, from: 'legend', pinned: [] }, 'speed_tram').size).toBe(0)
  })
})
