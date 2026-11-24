// Node detail: lazy loading of results/web/transfer_detail/<agg>.json and the pure models the card and the map
// draw. No React and no map here, so everything is testable. File format: docstring of pipeline/transfer_detail.py.
import { DATA_BASE_URL } from '../../config'

export const NO_DATA = 'brak danych'
export const DETAIL_DIR = 'transfer_detail/'

const MODES = { bus: 'autobus', tram: 'tramwaj', rail: 'kolej', metro: 'metro', trolleybus: 'trolejbus' }
export const modeText = (m) => MODES[m] || m || ''

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
const nf = (v, d) => new Intl.NumberFormat('pl-PL', { maximumFractionDigits: d, minimumFractionDigits: d, useGrouping: false }).format(v)
/** Minutes with one decimal, or "brak danych". */
export const minText = (v, unit = 'min') => (isNum(v) ? `${nf(v, 1)}${unit ? ` ${unit}` : ''}` : NO_DATA)
/** A fraction 0..1 as a whole percentage. */
export const pctText = (v) => (isNum(v) ? `${nf(v * 100, 0)} %` : NO_DATA)

/** "poznan-T00012" -> "poznan" (node ids carry their agglomeration). */
export const aggOfNode = (id) => {
  const s = String(id || '')
  const k = s.lastIndexOf('-T')
  return k > 0 ? s.slice(0, k) : null
}

/**
 * A loader with a cache per agglomeration file: the file is fetched the first time one of its nodes is asked for,
 * then reused. A failed fetch is not cached, so the next call tries again.
 *   const loader = createDetailLoader()
 *   const rec = await loader.get('poznan-T00012')   // the raw record, or null when the node has no detail
 * `fetchJson(url)` can be replaced (tests, another host); `base` is where the folder is served.
 */
export function createDetailLoader({ base = DATA_BASE_URL + DETAIL_DIR, fetchJson = defaultFetchJson } = {}) {
  const files = new Map()   // agg -> Promise<Map(id -> record)>
  const file = (agg) => {
    if (!files.has(agg)) {
      const p = fetchJson(`${base}${agg}.json`).then((doc) => {
        const m = new Map()
        for (const n of doc?.nodes || []) m.set(n.id, n)
        return m
      })
      p.catch(() => files.delete(agg))
      files.set(agg, p)
    }
    return files.get(agg)
  }
  return {
    /** Raw record of a node, or null when its file has no such node. Rejects when the file cannot be read. */
    async get(id) {
      const agg = aggOfNode(id)
      if (!agg) return null
      const m = await file(agg)
      return m.get(id) || null
    },
    /** Starts fetching a city's file ahead of a click (for example when the city is selected). */
    prefetch(agg) { if (agg) file(agg).catch(() => {}) },
    /** Agglomerations whose file is in the cache or on its way. */
    cached: () => [...files.keys()],
  }
}

async function defaultFetchJson(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`)
  return res.json()
}

/** "4 → Biskupin"; the line alone when the terminus is unknown. */
export const dirLabel = (line, term) => (term ? `${line?.label ?? '?'} → ${term}` : String(line?.label ?? '?'))

/** Flat [lon, lat, lon, lat, ...] -> [[lon, lat], ...]. */
export function pairs(flat) {
  const out = []
  for (let i = 0; i + 1 < (flat || []).length; i += 2) out.push([flat[i], flat[i + 1]])
  return out
}

/** The raw record decoded into objects that refer to each other. */
export function decodeNode(rec) {
  if (!rec) return null
  const lines = (rec.l || []).map(([label, mode], i) => ({ i, label, mode }))
  const dirs = (rec.d || []).map(([li, term, kind, n], i) => ({
    i, line: lines[li], term, kind, n, label: dirLabel(lines[li], term),
  }))
  const stops = (rec.s || []).map(([lon, lat, name, li], i) => ({ i, lon, lat, name, lines: (li || []).map((k) => lines[k]) }))
  const paths = (rec.p || []).map((p, i) => ({
    i, from: p.a, to: p.b, coords: pairs(p.g), m: p.m, min: p.t,
    xings: (p.x || []).map(([lon, lat, cls]) => ({ lon, lat, cls })),
    steps: (p.st || []).map(([lon, lat]) => ({ lon, lat })),
  }))
  const moves = (rec.mv || []).map(([f, t, p, walk, wait, conn, conn90, na, nb, w6], i) => ({
    i, from: dirs[f], to: dirs[t], path: p, walk, wait, conn, conn90, na, nb, trips: na * nb, w6,
  }))
  return {
    id: rec.id, name: rec.n, center: rec.c, dep: rec.dep, modes: String(rec.md || '').split(',').filter(Boolean),
    sum: rec.sum || {}, lines, dirs, stops, paths, moves,
    top: (rec.top || []).map((k) => moves[k]).filter(Boolean),
    rows: (rec.ar || []).map((k) => dirs[k]).filter(Boolean),
    cols: (rec.dp || []).map((k) => dirs[k]).filter(Boolean),
  }
}

/** The one plain sentence of the card: "Typowa przesiadka: X min dojścia + Y min czekania." */
export function summarySentence(node) {
  const s = node?.sum || {}
  if (!isNum(s.walk) || !isNum(s.wait)) return 'Typowej przesiadki w godzinach 7–9 nie da się tu policzyć: brak danych.'
  return `Typowa przesiadka: ${minText(s.walk)} dojścia + ${minText(s.wait)} czekania (7–9, średnia ważona liczbą kursów).`
}

/** Sum of a walk and a wait as printed: both parts rounded to 0.1, the total the sum of the printed parts. */
export function sumParts(walk, wait) {
  if (!isNum(walk) || !isNum(wait)) return null
  const a = Math.round(walk * 10) / 10
  const b = Math.round(wait * 10) / 10
  return { walk: a, wait: b, total: Math.round((a + b) * 10) / 10 }
}

// Colour classes of a matrix cell (walk + connection wait, min): the ramp of the map's "typowa przesiadka" layer.
export const CELL_STOPS = [6, 9, 12, 16]
export const CELL_COLORS = ['#4B3B8F', '#8A3F9E', '#C8508C', '#F0845C', '#FCD76B']
export function cellColor(total) {
  if (!isNum(total)) return null
  let k = 0
  while (k < CELL_STOPS.length && total >= CELL_STOPS[k]) k += 1
  return CELL_COLORS[k]
}

/**
 * The connection matrix: rows = arriving line and direction, columns = departing ones (heaviest first, as written by
 * the pipeline). A cell is {move, parts, color} for a movement, or {kind: 'same'} when the row and the column are the
 * same line, or {kind: 'none'} when there is no movement (the onward line goes where the first one continues, or back
 * where it came from: no reason to change there).
 */
export function matrixModel(node) {
  if (!node) return { rows: [], cols: [], cells: [] }
  const byKey = new Map(node.moves.map((m) => [`${m.from.i}:${m.to.i}`, m]))
  const cells = node.rows.map((r) => node.cols.map((c) => {
    if (r.line === c.line) return { kind: 'same' }
    const m = byKey.get(`${r.i}:${c.i}`)
    if (!m) return { kind: 'none' }
    const parts = sumParts(m.walk, m.conn)
    return { kind: 'move', move: m, parts, color: cellColor(parts?.total) }
  }))
  return { rows: node.rows, cols: node.cols, cells }
}

/** The generalised-time band as text, or null: "17,5–31,2 min (środek 26,2)". */
export function bandText(sum) {
  const g = sum?.gtt || []
  if (!isNum(g[0]) || !isNum(g[2])) return null
  return `${nf(g[0], 1)}–${nf(g[2], 1)} min (wariant środkowy ${isNum(g[1]) ? nf(g[1], 1) : NO_DATA})`
}

/** W6 classes: label, score and colour on the dark basemap (also used by the map layers). */
export const W6 = {
  grade: { label: 'bezkolizyjne (tunel, kładka)', score: '100 %', color: '#5FD08E' },
  signal: { label: 'z sygnalizacją', score: '70 lub 50 %', color: '#C5E36B' },
  zebra: { label: 'zebra bez sygnalizacji', score: '30 %', color: '#F2A93B' },
  unmarked: { label: 'niewyznakowane', score: '0 %', color: '#EF5B4C' },
  unknown: { label: 'bez klasy w OSM', score: 'bez oceny', color: '#8A909C' },
}
export const W6_ORDER = ['grade', 'signal', 'zebra', 'unmarked', 'unknown']

/** Obstacles: rows [label, value] for the card. */
export function obstacleRows(node) {
  const s = node?.sum || {}
  const w6 = s.w6 || []
  const counts = Object.fromEntries(W6_ORDER.map((k) => [k, 0]))
  for (const p of node?.paths || []) for (const x of p.xings) counts[x.cls] = (counts[x.cls] || 0) + 1
  return {
    rows: [
      ['Przejścia na ruch (średnia ważona kursami)', isNum(s.x) ? nf(s.x, 1) : NO_DATA],
      ['Bezpieczeństwo przejść, skala AMPTI W6', isNum(w6[0]) ? `${nf(w6[0], 0)} % (sygnalizacja jako 70 %), ${isNum(w6[1]) ? nf(w6[1], 0) : NO_DATA} % (jako 50 %)` : 'brak przejść z oceną'],
      ['Ruchy ze schodami', pctText(s.steps)],
      ['Ruchy z drogą bez schodów w OSM', pctText(s.free)],
      ['Ruchy, w których obie linie kursują co ≤ 10 min (7–9)', pctText(s.f10)],
    ],
    counts,
  }
}

/** Rows of the heaviest movements, in the shape the kit's DataTable takes (sortBy="column"). */
export function topMovementTable(node) {
  const n = (v, d = 1) => (isNum(v) ? { content: nf(v, d), value: v } : null)
  const columns = [
    { key: 'to', head: 'Na linię', align: 'left', first: 'asc' },
    { key: 'walk', head: 'Dojście, min', first: 'asc' },
    { key: 'wait', head: 'Czekanie (losowe przyjście), min', first: 'asc' },
    { key: 'conn', head: 'Czekanie na przesiadkę, mediana, min', first: 'asc' },
    { key: 'conn90', head: 'P90, min', first: 'asc' },
    { key: 'trips', head: 'Kursy (przyjazdy × odjazdy)' },
  ]
  const rows = (node?.top || []).map((m) => ({
    id: `mv${m.i}`, label: m.from.label, labelValue: m.from.label, move: m,
    cells: [
      { content: m.to.label, value: m.to.label }, n(m.walk), n(m.wait), n(m.conn), n(m.conn90),
      { content: `${m.na} × ${m.nb}`, value: m.trips },
    ],
  }))
  return { columns, rows }
}
