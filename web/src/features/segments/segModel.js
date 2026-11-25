// Stop-to-stop segments: the per-city detail document (results/web/speed/segments/<agg>.json, written by
// pipeline/speed_segments_web.py), the selection and its statistics. Pure functions, no DOM, no map.
// Every time and speed here is scheduled ("z rozkładu"), never measured.
import { BANDS, CLASS_COLORS, classOf } from '../speed/speedModel'

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

/** The free-running model's central parameters (tram_stretches.KIN) and the slider ranges of the what-if. */
export const CENTRAL = Object.freeze({ a_acc: 1.0, b_brk: 1.0, v_cap_kmh: 50, dwell_s: 20 })
export const RANGES = Object.freeze({
  dwell_s: [10, 40, 1], v_cap_kmh: [30, 70, 1], a_acc: [0.7, 1.3, 0.05], b_brk: [0.8, 1.3, 0.05],
})
/** The published range of the time above free running: every dwell x cap of this grid (central a, b). */
export const RANGE_DWELL = [10, 20, 30]
export const RANGE_CAP = [40, 50, 70]
export const PEAK = 'w_am'

// ------------------------------------------------------------------ free running (tram_stretches.free_time)
/** Free-running time, s, of a segment of `d` metres between two stops (accelerate, cap, brake) plus the dwell. */
export function freeTime(d, p) {
  const a = p.a_acc
  const b = p.b_brk
  const v = p.v_cap_kmh / 3.6
  const full = (v * v) / (2 * a) + (v * v) / (2 * b)
  let t
  if (d >= full) t = d / v + v / (2 * a) + v / (2 * b)
  else {
    const vp = Math.sqrt((Math.max(d, 0) * 2 * a * b) / (a + b))
    t = vp / a + vp / b
  }
  return t + p.dwell_s
}

/** Time-equivalent cap, km/h: OSM maxspeed on the share `msf` of the segment (harmonic mean `msh`), `v0` elsewhere. */
export const capKmh = (msh, msf, v0) => (isNum(msh) && msh > 0 && isNum(msf) && msf > 0 ? 1 / (msf / msh + (1 - msf) / v0) : v0)

/** Free-running time of one segment of the model with parameters `p`. */
export const segFree = (seg, p) => freeTime(seg.len, { ...p, v_cap_kmh: capKmh(seg.msh, seg.msf, p.v_cap_kmh) })

// ------------------------------------------------------------------ the document
/**
 * Columnar document -> {agg, code, keys, hours, model, places, segs, byId, lineDirs, patterns}. Each seg:
 * {i, id, a, b, len, stretch, pos, msh, msf, st, x, xs, xp, sw, bb, n: [per band], t: [per band, s], lines: [[ld, n[]]]}.
 */
export function parseDetail(doc) {
  const cols = doc.segments.columns
  const at = Object.fromEntries(cols.map((c, i) => [c, i]))
  const segs = doc.segments.rows.map((r, i) => ({
    i, id: r[at.id], a: r[at.a], b: r[at.b], len: r[at.len], stretch: r[at.stretch] ?? null, pos: r[at.pos] ?? null,
    msh: r[at.msh] ?? null, msf: r[at.msf] ?? null, st: r[at.st] ?? null, x: r[at.x] ?? null, xs: r[at.xs] ?? null,
    xp: r[at.xp] ?? null, sw: r[at.sw] ?? null, bb: r[at.bb] ?? null,
    n: doc.n[i], t: doc.t[i], lines: doc.seg_lines[i] || [],
  }))
  const keys = doc.bands.map((b) => b.key)
  return {
    agg: doc.agg, code: doc.code, mode: 'tram', keys, hours: doc.bands.map((b) => b.hours), model: doc.model || {},
    dates: doc.timetable_dates || null,
    places: doc.places, segs, byId: new Map(segs.map((s) => [s.id, s])), lineDirs: doc.line_dirs, patterns: doc.patterns,
  }
}

// ------------------------------------------------------------------ selection operations
/** Click on a segment: add it, or take it out when it is already selected. */
export const toggleId = (ids, id) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id])
/** Union in order: the selection, then the new ids not yet in it. */
export const addIds = (ids, more) => [...ids, ...more.filter((x) => !ids.includes(x))]

/** The ids of the stretch ("odcinek między węzłami") a segment belongs to, in order; [id] when it is on none. */
export function stretchIds(model, id) {
  const s = model.byId.get(id)
  if (!s) return []
  if (!s.stretch) return [id]
  return model.segs.filter((x) => x.stretch === s.stretch).sort((p, q) => (p.pos ?? 0) - (q.pos ?? 0)).map((x) => x.id)
}

const lineKey = (s) => { const n = Number(s); return Number.isFinite(n) ? [0, n, s] : [1, 0, s] }
const byLine = (p, q) => { const a = lineKey(p); const b = lineKey(q); return a[0] - b[0] || a[1] - b[1] || String(a[2]).localeCompare(String(b[2])) }

/** Line directions running on a segment, most trips first in the band: [{ld, line, d, name, n}]. */
export function linesAt(model, id, band) {
  const s = model.byId.get(id)
  if (!s) return []
  const j = model.keys.indexOf(band)
  const ja = model.keys.indexOf(band?.startsWith('s_') ? 's_all' : 'w_all')
  return s.lines.map(([ld, n]) => ({ ld, ...pick(model.lineDirs[ld]), n: n[j] ?? 0, nAll: n[ja] ?? 0 }))
    .filter((x) => x.nAll > 0 || x.n > 0)
    .sort((p, q) => byLine(p.line, q.line) || p.d.localeCompare(q.d))
}
const pick = (x) => ({ line: x.line, d: x.d, name: x.name })

/** The segments of the most frequent pattern of line direction `ld` that runs on segment `id` (the line "in this direction"). */
export function patternIds(model, id, ld) {
  const s = model.byId.get(id)
  if (!s) return []
  const cands = model.patterns.filter((p) => p.ld === ld && p.s.includes(s.i))
  if (!cands.length) return [id]
  cands.sort((p, q) => (q.nw - p.nw) || (q.ns - p.ns) || (q.s.length - p.s.length))
  return cands[0].s.map((i) => model.segs[i].id)
}

/**
 * How the selected segments hang together: `pieces` = number of chains they form (segments that follow one another
 * head to tail, a reversal A->B->A does not join), `chain` = true for one chain in one direction without branches,
 * `order` = its segments in running order (or null).
 */
export function structure(segs) {
  const ins = new Map()
  const outs = new Map()
  for (const s of segs) {
    if (!ins.has(s.b)) ins.set(s.b, [])
    ins.get(s.b).push(s)
    if (!outs.has(s.a)) outs.set(s.a, [])
    outs.get(s.a).push(s)
  }
  let joins = 0
  for (const [node, I] of ins) {
    const O = outs.get(node) || []
    let j = Math.min(I.length, O.length)
    if (j === 1 && I.length === 1 && O.length === 1 && I[0].a === O[0].b) j = 0   // A -> B -> A is not one run
    joins += j
  }
  const pieces = segs.length ? Math.max(1, segs.length - joins) : 0
  const simple = [...ins.values()].every((x) => x.length <= 1) && [...outs.values()].every((x) => x.length <= 1)
  let order = null
  if (pieces === 1 && simple) {
    const ends = new Set(segs.map((s) => s.b))
    const start = segs.find((s) => !ends.has(s.a)) || null
    if (start) {
      order = [start]
      const seen = new Set([start.id])
      let cur = start
      while (outs.get(cur.b)?.length) {
        const nx = outs.get(cur.b)[0]
        if (seen.has(nx.id) || nx.a === cur.b && nx.b === cur.a) break
        order.push(nx); seen.add(nx.id); cur = nx
      }
      if (order.length !== segs.length) order = null
    }
  }
  return { pieces, chain: !!order, order }
}

// ------------------------------------------------------------------ statistics of a selection
/** Speed interval, km/h, of `lengthM` run in `timeS` when the time may be off by +-`errMin` minutes. */
export function speedInterval(lengthM, timeS, errMin) {
  if (!isNum(lengthM) || !isNum(timeS) || timeS <= 0 || lengthM <= 0) return null
  const e = errMin * 60
  return { lo: (lengthM / (timeS + e)) * 3.6, hi: timeS > e ? (lengthM / (timeS - e)) * 3.6 : null }
}

const sum = (xs) => xs.reduce((a, b) => a + b, 0)

/** Time above free running of segments in band j with params p: {taf s/km, faster, lo, hi} (range over the grid). */
export function tafOf(segs, j, p = CENTRAL) {
  const served = segs.filter((s) => isNum(s.t[j]) && isNum(s.len))
  if (!served.length) return null
  const T = sum(served.map((s) => s.t[j]))
  const km = sum(served.map((s) => s.len)) / 1000
  const F = sum(served.map((s) => segFree(s, p)))
  if (T - F < 0) return { taf: null, faster: true, lo: null, hi: null, free: F, T, km }
  const vals = []
  for (const d of RANGE_DWELL) {
    for (const c of RANGE_CAP) vals.push((T - sum(served.map((s) => segFree(s, { ...p, dwell_s: d, v_cap_kmh: c })))) / km)
  }
  return { taf: (T - F) / km, faster: false, lo: Math.max(0, Math.min(...vals)), hi: Math.max(0, Math.max(...vals)), free: F, T, km }
}

/** Length-weighted OSM attributes of segments; null fields where no segment has the value. */
export function osmOf(segs) {
  const withSt = segs.filter((s) => isNum(s.st) && isNum(s.len))
  const L = sum(withSt.map((s) => s.len))
  const tot = (k) => (segs.some((s) => isNum(s[k])) ? sum(segs.filter((s) => isNum(s[k])).map((s) => s[k])) : null)
  return {
    st: L > 0 ? sum(withSt.map((s) => s.st * s.len)) / L : null,
    x: tot('x'), xs: tot('xs'), xp: tot('xp'), sw: tot('sw'),
    complete: segs.every((s) => isNum(s.x)),
  }
}

/**
 * Everything the panel says about a tram selection in a band: what is selected, time, speed and its rounding interval,
 * trips per hour, lines, time above free running, OSM attributes, and the speed per band (strip).
 */
export function summary(model, ids, band, p = CENTRAL) {
  const segs = ids.map((id) => model.byId.get(id)).filter(Boolean)
  if (!segs.length) return null
  const j = model.keys.indexOf(band)
  const st = structure(segs)
  const nodes = new Set(segs.flatMap((s) => [s.a, s.b]))
  const served = segs.filter((s) => isNum(s.t[j]))
  const L = sum(segs.map((s) => s.len || 0))
  const Ls = sum(served.map((s) => s.len || 0))
  const T = served.length ? sum(served.map((s) => s.t[j])) : null
  const servedSt = served.length === segs.length ? st : structure(served)
  const v = T && T > 0 ? (Ls / T) * 3.6 : null
  const iv = T != null ? speedInterval(Ls, T, servedSt.pieces) : null
  const tph = served.map((s) => s.n[j] / model.hours[j]).filter(isNum)
  const lineSet = new Map()
  for (const s of served) {
    for (const [ld, n] of s.lines) {
      if (!(n[j] > 0)) continue
      const x = model.lineDirs[ld]
      lineSet.set(x.line, (lineSet.get(x.line) || 0) + n[j])
    }
  }
  const strip = BANDS.filter((b) => !b.key.endsWith('_all')).map((b) => {
    const k = model.keys.indexOf(b.key)
    const sv = segs.filter((s) => isNum(s.t[k]))
    const tt = sum(sv.map((s) => s.t[k]))
    // as in the summary: the segments with trips in the band; `partial` when some have none
    const val = sv.length && tt > 0 ? (sum(sv.map((s) => s.len)) / tt) * 3.6 : null
    const c = classOf(val)
    return { key: b.key, value: val, cls: c, color: c >= 0 ? CLASS_COLORS[c] : null, partial: !!sv.length && sv.length < segs.length }
  })
  return {
    count: segs.length, lengthM: L, stops: nodes.size, pieces: st.pieces, chain: st.chain,
    names: st.order ? [model.places[st.order[0].a], ...st.order.map((s) => model.places[s.b])] : null,
    served: served.length, servedLengthM: Ls, timeS: T, speed: v, interval: iv, errMin: servedSt.pieces,
    zeroTime: T === 0,
    tph: tph.length ? { min: Math.min(...tph), max: Math.max(...tph) } : null,
    lines: [...lineSet.keys()].sort(byLine),
    taf: tafOf(segs, j, p), osm: osmOf(segs), strip,
  }
}

// ------------------------------------------------------------------ what if
/**
 * Savings per segment in band j: plan {mode: 'share', share 0..1} takes that share of each segment's time above free
 * running; {mode: 'target', target km/h} brings the selection to the target speed, the saving taken from the segments
 * in proportion to their time above free running. No segment gets faster than its own free-running time (the rule of
 * pipeline/whatif_tram.py); the selection never gets slower. Returns [saving s per segment] (0 where nothing changes).
 */
export function savings(segs, j, p, plan) {
  const t = segs.map((s) => (isNum(s.t[j]) ? s.t[j] : null))
  const F = segs.map((s) => segFree(s, p))
  const slack = t.map((x, i) => (x == null ? 0 : Math.max(0, x - F[i])))
  if (plan.mode === 'share') {
    const k = Math.min(1, Math.max(0, plan.share))
    return slack.map((x) => x * k)
  }
  const idx = t.map((x, i) => (x == null ? -1 : i)).filter((i) => i >= 0)
  if (!idx.length || !(plan.target > 0)) return segs.map(() => 0)
  const S = sum(idx.map((i) => t[i]))
  const L = sum(idx.map((i) => segs[i].len))
  const Fs = sum(idx.map((i) => F[i]))
  const goal = Math.max(L / (plan.target / 3.6), Fs)
  const D = Math.max(0, S - goal)
  const tot = sum(slack)
  if (D <= 0 || tot <= 0) return segs.map(() => 0)
  const k = Math.min(1, D / tot)
  return slack.map((x) => x * k)
}

/**
 * The what-if for a tram selection: per band the new time and speed of the selection and the seconds saved per run;
 * per line direction that uses it the mean saving per trip, the new end-to-end scheduled speed, vehicle-hours saved
 * on a weekday and vehicles freed in the morning peak at unchanged frequency (idealised); and the totals.
 */
export function whatIf(model, ids, p, plan) {
  const segs = ids.map((id) => model.byId.get(id)).filter(Boolean)
  if (!segs.length) return null
  const bands = []
  const perLd = new Map()
  let vehH = 0
  let vehPeak = null
  model.keys.forEach((key, j) => {
    if (key.endsWith('_all')) return
    const s = savings(segs, j, p, plan)
    const served = segs.map((x, i) => i).filter((i) => isNum(segs[i].t[j]))
    const T = served.length ? sum(served.map((i) => segs[i].t[j])) : null
    const saved = served.length ? sum(served.map((i) => s[i])) : null
    const L = sum(served.map((i) => segs[i].len))
    const veh = served.length ? sum(served.map((i) => s[i] * (segs[i].n[j] || 0))) / 3600 : null   // vehicle-hours in the band
    bands.push({
      key, timeS: T, newTimeS: T != null ? T - saved : null, savedS: saved,
      speed: T > 0 ? (L / T) * 3.6 : null, newSpeed: T != null && T - saved > 0 ? (L / (T - saved)) * 3.6 : null,
      vehHours: veh,
    })
    if (key.startsWith('w_') && veh != null) vehH += veh
    if (key === PEAK) vehPeak = veh != null ? veh / model.hours[j] : null
    // per line direction
    segs.forEach((g, i) => {
      for (const [ld, n] of g.lines) {
        if (!(n[j] > 0)) continue
        if (!perLd.has(ld)) perLd.set(ld, { ld, sv: {}, cap: {} })
        const e = perLd.get(ld)
        e.sv[key] = (e.sv[key] || 0) + s[i] * n[j]
        e.cap[key] = (e.cap[key] || 0) + s[i]
      }
    })
  })
  const lines = [...perLd.values()].map((e) => {
    const x = model.lineDirs[e.ld]
    const per = model.keys.map((key, j) => {
      if (key.endsWith('_all') || e.sv[key] == null) return null
      const N = x.trips[j]
      const save = N > 0 ? Math.min(e.sv[key] / N, e.cap[key]) : null
      const Lx = x.len[j]
      const Tx = x.time[j]
      return {
        key, savedS: save,
        speed: isNum(Lx) && Tx > 0 ? (Lx / Tx) * 3.6 : null,
        newSpeed: isNum(Lx) && Tx > 0 && save != null && Tx - save > 0 ? (Lx / (Tx - save)) * 3.6 : null,
      }
    })
    // no Wednesday trips of this line direction here: no number (not 0)
    const wd = model.keys.filter((key) => key.startsWith('w_') && !key.endsWith('_all') && e.sv[key] != null)
    const vh = wd.length ? sum(wd.map((key) => e.sv[key])) / 3600 : null
    const jp = model.keys.indexOf(PEAK)
    const vp = e.sv[PEAK] != null ? e.sv[PEAK] / model.hours[jp] / 3600 : null
    return { ld: e.ld, line: x.line, d: x.d, name: x.name, per, vehHours: vh, vehPeak: vp }
  }).sort((p1, q) => byLine(p1.line, q.line) || p1.d.localeCompare(q.d))
  return { bands, lines, vehHoursWeekday: vehH, vehiclesPeak: vehPeak }
}

// ------------------------------------------------------------------ bus, metro and rail (features, no detail file)
/**
 * The same summary for features of the stretch / line layers (bus stretches, metro and rail lines), from their map
 * properties only: no free-running model, no OSM. Each feature is its own piece of the +-1 minute rule.
 */
export function featureSummary(props, band) {
  if (!props.length) return null
  const kv = `v_${band}`
  const kt = `t_${band}`
  const withLen = props.filter((p) => isNum(p.len))
  const served = withLen.filter((p) => isNum(p[kv]) && p[kv] > 0)
  const L = sum(served.map((p) => p.len))
  const T = served.length ? sum(served.map((p) => p.len / (p[kv] / 3.6))) : null
  const tph = props.map((p) => p[kt]).filter(isNum)
  const lines = new Set()
  for (const p of props) for (const l of String(p.ln || '').split(',').map((s) => s.trim()).filter(Boolean)) lines.add(l)
  const speeds = props.map((p) => p[kv]).filter(isNum)
  return {
    count: props.length, lengthM: withLen.length === props.length ? sum(withLen.map((p) => p.len)) : null,
    servedLengthM: L, timeS: T, speed: T > 0 ? (L / T) * 3.6 : (speeds.length === 1 ? speeds[0] : null),
    interval: T > 0 ? speedInterval(L, T, served.length) : null, errMin: served.length,
    tph: tph.length ? { min: Math.min(...tph), max: Math.max(...tph) } : null,
    lines: [...lines].sort(byLine), names: props.length === 1 && props[0].stops ? String(props[0].stops).split(' > ') : null,
    hasLength: withLen.length > 0, speeds,
  }
}

/** Bounding box [w, s, e, n] of tram segments (their `bb`), or null. */
export function boundsOf(segs) {
  const bs = segs.map((s) => s.bb).filter((b) => Array.isArray(b) && b.length === 4)
  if (!bs.length) return null
  return [Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))]
}

/** Bounding box of GeoJSON LineString features, or null. */
export function featureBounds(features) {
  let w = Infinity; let s = Infinity; let e = -Infinity; let n = -Infinity
  for (const f of features) {
    for (const [x, y] of f?.geometry?.coordinates || []) {
      if (x < w) w = x; if (x > e) e = x; if (y < s) s = y; if (y > n) n = y
    }
  }
  return Number.isFinite(w) ? [w, s, e, n] : null
}

// ------------------------------------------------------------------ the address
const MODES = ['tram', 'bus', 'rail']
/** "tram:WRO-042f6,WRO-08138" -> {mode, ids}; anything else null. */
export function parseSel(text) {
  if (!text) return null
  const i = text.indexOf(':')
  const mode = i > 0 ? text.slice(0, i) : ''
  if (!MODES.includes(mode)) return null
  // rail ids contain ':' themselves, so they are separated by ',' only
  const ids = text.slice(i + 1).split(',').map((s) => s.trim()).filter(Boolean)
  return ids.length ? { mode, ids: [...new Set(ids)] } : null
}
/** {mode, ids} -> "tram:id,id" ('' for none). */
export const selText = (sel) => (sel && MODES.includes(sel.mode) && sel.ids?.length ? `${sel.mode}:${sel.ids.join(',')}` : '')

/** The agglomeration of a selection: from the city code of a tram or bus id, or the prefix of a rail id. */
export function aggOfSel(sel, codes) {
  if (!sel || !sel.ids.length) return null
  const id = sel.ids[0]
  if (sel.mode === 'rail') return id.split(':')[0] || null
  const code = id.split('-')[0]
  return Object.entries(codes).find(([, c]) => c === code)?.[0] ?? null
}
export const CITY_CODES = Object.freeze({
  warszawa: 'WAW', krakow: 'KRK', wroclaw: 'WRO', poznan: 'POZ', lodz: 'LDZ', trojmiasto: 'GDN', gzm: 'GZM',
})
