import { describe, expect, it } from 'vitest'
import {
  CENTRAL, addIds, aggOfSel, capKmh, CITY_CODES, featureSummary, freeTime, linesAt, parseDetail, parseSel, patternIds,
  savings, segFree, selText, speedInterval, stretchIds, structure, summary, toggleId, whatIf,
} from './segModel'
import { duration, nf, tipModel } from './segText'
import { freeArea, panToShow } from './segMap'

// reference values from pipeline/tram_stretches.free_time (python, the same segments of the published files)
const ALT = { dwell_s: 10, v_cap_kmh: 70, a_acc: 1.3, b_brk: 0.8 }
const PY = [
  { id: 'WRO-042f6', len: 557.2, msh: 30.0, msf: 0.08929, p: {}, free: 75.615094 },
  { id: 'WRO-042f6', len: 557.2, msh: 30.0, msf: 0.08929, p: ALT, free: 59.610465 },
  { id: 'WRO-08138', len: 658.9, msh: 30.0, msf: 0.2121, p: {}, free: 86.317221 },
  { id: 'WRO-00e87', len: 459.8, msh: null, msf: 0, p: {}, free: 66.994489 },
  { id: 'WRO-02fc1', len: 759.2, msh: null, msf: 0, p: ALT, free: 68.675982 },
  { id: 'WRO-e401e', len: 34.28, msh: null, msf: 0, p: {}, free: 31.709825 },
  { id: 'WRO-e401e', len: 34.28, msh: null, msf: 0, p: ALT, free: 21.765987 },
  { id: 'KRK-0052d', len: 239.9, msh: 45.28, msf: 1.0, p: {}, free: 51.651099 },
  { id: 'KRK-0227e', len: 666.6, msh: 50.0, msf: 1.0, p: ALT, free: 72.017636 },
  { id: 'KRK-bad6e', len: 161.0, msh: null, msf: 0, p: {}, free: 45.377155 },
]

describe('free running', () => {
  it('gives the same seconds as tram_stretches.free_time', () => {
    for (const c of PY) {
      const seg = { len: c.len, msh: c.msh, msf: c.msf }
      expect(segFree(seg, { ...CENTRAL, ...c.p })).toBeCloseTo(c.free, 4)
    }
  })
  it('uses the OSM cap only where tagged', () => {
    expect(capKmh(null, 0, 50)).toBe(50)
    expect(capKmh(30, 1, 50)).toBeCloseTo(30, 10)
    expect(capKmh(30, 0.5, 50)).toBeCloseTo(1 / (0.5 / 30 + 0.5 / 50), 10)
  })
  it('short segments never reach the cap', () => {
    const p = { ...CENTRAL, dwell_s: 0 }
    expect(freeTime(100, p)).toBeCloseTo(2 * Math.sqrt(100), 6)   // a = b = 1: v_peak = sqrt(d), t = 2 v_peak
  })
})

// a tiny city: places 0 > 1 > 2 > 3 one way, 1 > 0 back; bands w_am (index 0, 2 h) and w_md (index 1, 6 h)
const DOC = {
  agg: 'wroclaw', code: 'WRO', timetable_dates: { weekday: '2026-11-25', saturday: '2026-11-28' },
  bands: [{ key: 'w_am', hours: 2 }, { key: 'w_md', hours: 6 }, { key: 'w_all', hours: 24 }],
  places: ['Rynek', 'Plac', 'Most', 'Pętla'],
  segments: {
    columns: ['id', 'a', 'b', 'len', 'stretch', 'pos', 'msh', 'msf', 'st', 'x', 'xs', 'xp', 'sw', 'bb'],
    rows: [
      ['WRO-aaaaa', 0, 1, 500, 'WRO-s1-A', 0, null, 0, 0.5, 2, 1, 0, 1, [17.0, 51.0, 17.01, 51.01]],
      ['WRO-bbbbb', 1, 2, 400, 'WRO-s1-A', 1, null, 0, 0, 1, 1, 1, 0, [17.01, 51.0, 17.02, 51.01]],
      ['WRO-ccccc', 2, 3, 600, null, null, 50, 1, 1, 0, 0, 0, 2, [17.02, 51.0, 17.03, 51.02]],
      ['WRO-ddddd', 1, 0, 500, 'WRO-s1-B', 1, null, 0, 0.5, 2, 1, 0, 1, [17.0, 51.0, 17.01, 51.01]],
    ],
  },
  n: [[20, 30, 200], [20, 30, 200], [10, 30, 100], [20, 30, 200]],
  t: [[120, 90, 100], [60, 60, 60], [120, null, 120], [120, 90, 100]],
  seg_lines: [
    [[0, [20, 30, 200]]],
    [[0, [10, 15, 100]], [1, [10, 15, 100]]],
    [[0, [10, 30, 100]]],
    [[2, [20, 30, 200]]],
  ],
  line_dirs: [
    { line: '3', d: '0', name: 'Rynek → Pętla', trips: [20, 30, 200], len: [8000, 8000, 8000], time: [1800, 1700, 1750] },
    { line: '5', d: '0', name: 'Plac → Most', trips: [10, 15, 100], len: [5000, 5000, 5000], time: [1200, 1100, 1150] },
    { line: '3', d: '1', name: 'Pętla → Rynek', trips: [20, 30, 200], len: [8000, 8000, 8000], time: [1800, 1700, 1750] },
  ],
  patterns: [
    { line: '3', d: '0', ld: 0, s: [0, 1, 2], nw: 150, ns: 80 },
    { line: '3', d: '0', ld: 0, s: [0, 1], nw: 50, ns: 0 },
    { line: '5', d: '0', ld: 1, s: [1], nw: 100, ns: 0 },
  ],
}
const M = parseDetail(DOC)

describe('selection', () => {
  it('toggles and extends', () => {
    expect(toggleId(['a'], 'b')).toEqual(['a', 'b'])
    expect(toggleId(['a', 'b'], 'a')).toEqual(['b'])
    expect(addIds(['a'], ['b', 'a', 'c'])).toEqual(['a', 'b', 'c'])
  })
  it('finds the stretch and the main pattern of a line', () => {
    expect(stretchIds(M, 'WRO-bbbbb')).toEqual(['WRO-aaaaa', 'WRO-bbbbb'])
    expect(stretchIds(M, 'WRO-ccccc')).toEqual(['WRO-ccccc'])
    expect(patternIds(M, 'WRO-bbbbb', 0)).toEqual(['WRO-aaaaa', 'WRO-bbbbb', 'WRO-ccccc'])
    expect(linesAt(M, 'WRO-bbbbb', 'w_am').map((l) => l.line)).toEqual(['3', '5'])
  })
  it('tells one chain from several pieces; a reversal does not join', () => {
    const [a, b, c, d] = M.segs
    expect(structure([c, a, b])).toMatchObject({ pieces: 1, chain: true })
    expect(structure([c, a, b]).order.map((s) => s.id)).toEqual([a.id, b.id, c.id])
    expect(structure([a, c])).toMatchObject({ pieces: 2, chain: false })
    expect(structure([a, d])).toMatchObject({ pieces: 2, chain: false })
  })
})

describe('summary', () => {
  it('sums a chain with one +-1 min interval at its ends', () => {
    const s = summary(M, ['WRO-aaaaa', 'WRO-bbbbb', 'WRO-ccccc'], 'w_am')
    expect(s.count).toBe(3)
    expect(s.lengthM).toBe(1500)
    expect(s.stops).toBe(4)
    expect(s.names).toEqual(['Rynek', 'Plac', 'Most', 'Pętla'])
    expect(s.timeS).toBe(300)
    expect(s.speed).toBeCloseTo(18, 6)
    expect(s.errMin).toBe(1)
    expect(s.interval.lo).toBeCloseTo((1500 / 360) * 3.6, 6)
    expect(s.interval.hi).toBeCloseTo((1500 / 240) * 3.6, 6)
    expect(s.lines).toEqual(['3', '5'])
    expect(s.tph).toEqual({ min: 5, max: 10 })
    expect(s.osm.x).toBe(3)
    expect(s.osm.st).toBeCloseTo((0.5 * 500 + 0 + 600) / 1500, 6)
  })
  it('widens the interval by a minute per piece and leaves out segments without trips', () => {
    const s = summary(M, ['WRO-aaaaa', 'WRO-ccccc'], 'w_md')
    expect(s.served).toBe(1)
    expect(s.timeS).toBe(90)
    expect(s.errMin).toBe(1)
    const s2 = summary(M, ['WRO-aaaaa', 'WRO-ccccc'], 'w_am')
    expect(s2.errMin).toBe(2)
    expect(s2.interval.hi).toBeCloseTo((1100 / (240 - 120)) * 3.6, 6)
  })
  it('one short segment: no upper bound', () => {
    expect(speedInterval(400, 60, 1).hi).toBeNull()
  })
})

describe('what if', () => {
  const ids = ['WRO-aaaaa', 'WRO-bbbbb', 'WRO-ccccc']
  it('never makes a segment faster than free running', () => {
    const j = 0
    const s = savings(M.segs.slice(0, 3), j, CENTRAL, { mode: 'share', share: 1 })
    M.segs.slice(0, 3).forEach((g, i) => {
      expect(g.t[j] - s[i]).toBeGreaterThanOrEqual(Math.min(g.t[j], segFree(g, CENTRAL)) - 1e-9)
    })
    // an impossible target stops at the free-running time of the whole selection (whatif_tram: S* = max(L / v*, F));
    // a segment already faster than the model (here the 60 s one) is left alone and does not count as a reserve
    const segs = M.segs.slice(0, 3)
    const huge = savings(segs, j, CENTRAL, { mode: 'target', target: 500 })
    const F = segs.reduce((a, g) => a + segFree(g, CENTRAL), 0)
    expect(300 - huge.reduce((a, b) => a + b, 0)).toBeCloseTo(F, 6)
    expect(huge[1]).toBe(0)
    huge.forEach((x, i) => expect(x).toBeLessThanOrEqual(s[i] + 1e-9))
  })
  it('reaches a modest target exactly and never slows down', () => {
    const segs = M.segs.slice(0, 3)
    const s = savings(segs, 0, CENTRAL, { mode: 'target', target: 20 })
    expect(300 - s.reduce((a, b) => a + b, 0)).toBeCloseTo(1500 / (20 / 3.6), 6)
    expect(savings(segs, 0, CENTRAL, { mode: 'target', target: 10 })).toEqual([0, 0, 0])
  })
  it('counts vehicle-hours over the weekday bands and vehicles in the morning peak', () => {
    const w = whatIf(M, ids, CENTRAL, { mode: 'share', share: 0.5 })
    const am = savings(M.segs.slice(0, 3), 0, CENTRAL, { mode: 'share', share: 0.5 })
    const md = savings(M.segs.slice(0, 3), 1, CENTRAL, { mode: 'share', share: 0.5 })
    const vhAm = (am[0] * 20 + am[1] * 20 + am[2] * 10) / 3600
    const vhMd = (md[0] * 30 + md[1] * 30) / 3600
    expect(w.vehHoursWeekday).toBeCloseTo(vhAm + vhMd, 9)
    expect(w.vehiclesPeak).toBeCloseTo(vhAm / 2, 9)
    const l3 = w.lines.find((l) => l.line === '3' && l.d === '0')
    const x = l3.per.find((q) => q?.key === 'w_am')
    expect(x.savedS).toBeCloseTo((am[0] * 20 + am[1] * 10 + am[2] * 10) / 20, 9)
    expect(x.newSpeed).toBeGreaterThan(x.speed)
  })
})

describe('address', () => {
  it('reads and writes the selection', () => {
    expect(parseSel('tram:WRO-aaaaa,WRO-bbbbb')).toEqual({ mode: 'tram', ids: ['WRO-aaaaa', 'WRO-bbbbb'] })
    expect(parseSel('rail:warszawa:wkd:WKD')).toEqual({ mode: 'rail', ids: ['warszawa:wkd:WKD'] })
    expect(parseSel('boat:x')).toBeNull()
    expect(parseSel('')).toBeNull()
    expect(selText({ mode: 'tram', ids: ['a', 'b'] })).toBe('tram:a,b')
    expect(selText(null)).toBe('')
    expect(aggOfSel({ mode: 'tram', ids: ['KRK-0052d'] }, CITY_CODES)).toBe('krakow')
    expect(aggOfSel({ mode: 'bus', ids: ['GDN-b1234abcd-A'] }, CITY_CODES)).toBe('trojmiasto')
    expect(aggOfSel({ mode: 'rail', ids: ['warszawa:wkd:WKD'] }, CITY_CODES)).toBe('warszawa')
  })
})

describe('words and the map', () => {
  it('formats in Polish', () => {
    expect(nf(1234.5, 1)).toMatch(/^1\s234,5$/)
    expect(duration(125)).toBe('2 min 5 s')
    expect(duration(45)).toBe('45 s')
  })
  it('builds the tooltip with the interval and trips', () => {
    const t = tipModel({ name: 'A → B', m: 'tram', len: 500, v_w_am: 15, t_w_am: 12 }, 'w_am')
    expect(t.title).toBe('A → B')
    expect(t.lines[0]).toMatch(/^15 km\/h z rozkładu \(±1 min: /)
    expect(t.lines[1]).toBe('12 kursów na godzinę')
    expect(tipModel({ name: 'x', m: 'tram', len: 500 }, 'w_am').lines[0]).toBe('brak kursów w tym paśmie')
  })
  it('keeps a selection clear of the panel', () => {
    const area = freeArea({ left: 0, top: 0, width: 1000, height: 600 }, { left: 600, top: 10, width: 380, height: 550 })
    expect(area.right).toBe(584)
    expect(panToShow({ left: 500, right: 700, top: 100, bottom: 200 }, area)).toEqual([116, 0])
    expect(panToShow({ left: 0, right: 900, top: 100, bottom: 200 }, area)).toBeNull()
    const sheet = freeArea({ left: 0, top: 0, width: 375, height: 800 }, { left: 0, top: 400, width: 375, height: 400 })
    expect(sheet.bottom).toBe(384)
  })
  it('sums bus stretches from their map properties', () => {
    const s = featureSummary([
      { id: 'a', len: 1000, v_w_am: 20, t_w_am: 6, ln: ',1,2,' },
      { id: 'b', len: 2000, v_w_am: 30, t_w_am: 10, ln: ',2,' },
    ], 'w_am')
    expect(s.timeS).toBeCloseTo(180 + 240, 6)
    expect(s.errMin).toBe(2)
    expect(s.lines).toEqual(['1', '2'])
  })
})
