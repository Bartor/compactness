// The popup of a stop area: pure model from the feature's properties, and a DOM builder (no innerHTML,
// names come from data).
export const NO_DATA = 'brak danych'

const MODES = { bus: 'autobus', tram: 'tramwaj', rail: 'kolej', metro: 'metro', trolleybus: 'trolejbus' }

/** "bus,tram" -> "autobus, tramwaj" */
export const modesText = (modes) => String(modes || '').split(',').filter(Boolean).map((m) => MODES[m] || m).join(', ')

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
const nf = (v, d) => new Intl.NumberFormat('pl-PL', { maximumFractionDigits: d, useGrouping: false }).format(v)

/** Number with a unit, or "brak danych". */
export const num = (v, unit = '', d = 1) => (isNum(v) ? `${nf(v, d)}${unit ? ` ${unit}` : ''}` : NO_DATA)
/** A share given as a fraction 0..1, as a whole percentage. */
export const pct = (v) => (isNum(v) ? `${nf(v * 100, 0)} %` : NO_DATA)

/**
 * The additive 7–9 line: "dojście X min + czekanie Y min = Z min" with the parts rounded to 0.1 min and Z the sum
 * of the printed parts, so the line always adds up; "brak danych" when a part is missing.
 */
export function transferSumText(walk, wait) {
  if (!isNum(walk) || !isNum(wait)) return NO_DATA
  const a = Math.round(walk * 10) / 10
  const b = Math.round(wait * 10) / 10
  const z = Math.round((a + b) * 10) / 10
  return `dojście ${nf(a, 1)} min + czekanie ${nf(b, 1)} min = ${nf(z, 1)} min`
}

/** A share with one decimal below 10 %: "0,1 %", "6,3 %", "24 %". */
export const shareText = (v) => (isNum(v) ? `${nf(v * 100, v < 0.1 ? 1 : 0)} %` : NO_DATA)

export const SUM_LABEL = 'Typowa przesiadka 7–9 (średnia ważona liczbą kursów)'

/**
 * {title, modes, sections: [{title, rows: [[label, value]]}], notes: [text], footer}.
 * Properties are those of results/web/transfer_nodes.geojson (shares are fractions).
 */
export function nodePopupModel(p, timetableDate) {
  const excl = isNum(p.pairs_excl) && p.pairs_excl > 0 ? ` (bez ${nf(p.pairs_excl, 0)} par linii jadących tą samą trasą)` : ''
  const pairs = isNum(p.pairs) ? `${nf(p.pairs, 0)}${excl}` : NO_DATA
  const sections = [
    {
      title: 'Typowa przesiadka',
      rows: [[SUM_LABEL, transferSumText(p.walk_w, p.wait_w)]],
    },
    {
      title: 'Znaczenie',
      rows: [
        ['Linie', num(p.lines, '', 0)],
        ['Pary przesiadkowe', pairs],
        ['Odjazdy na godzinę, 6–20', num(p.dep_h)],
        ['Odjazdy na godzinę, 7–9', num(p.dep_h_am)],
      ],
    },
    {
      title: 'Dojście (mediany)',
      rows: [
        ['Z kierunkami, mediana', num(p.walk_dir, 'min')],
        ['Z kierunkami, co dziesiąte dłuższe niż', num(p.walk_dir_p90, 'min')],
        ['Najlepsza para, mediana', num(p.walk_best, 'min')],
      ],
    },
    {
      title: 'Przeszkody',
      rows: [
        ['Przejścia przez jezdnię, mediana', num(p.cross)],
        ['Przejścia z sygnalizacją', pct(p.cross_signal)],
        ['Ruchy ze schodami', pct(p.steps)],
        ['Droga bez schodów w OSM', isNum(p.stepfree) ? `${pct(p.stepfree)} ruchów` : NO_DATA],
      ],
    },
    {
      title: 'Czekanie (mediany)',
      rows: [
        ['7–9, mediana', num(p.wait_am, 'min')],
        ['6–20, mediana', num(p.wait_day, 'min')],
      ],
    },
    {
      title: 'Dojście + czekanie 7–9 (mediany, nie sumują się z wierszami wyżej)',
      rows: [
        ['Mediana po parach linii', num(p.walkwait_am, 'min')],
        ['Najlepsza para, mediana ważona liczbą kursów', num(p.walkwait_am_w, 'min')],
      ],
    },
  ]
  // newer data: connection wait, the generalised-time band, crossing safety, frequent pairs (blocks without data are left out)
  const has = (...keys) => keys.some((k) => isNum(p[k]))
  if (has('conn_w', 'conn_med', 'conn_p90')) {
    sections.splice(1, 0, {
      title: 'Czekanie po przyjeździe linii dowożącej (7–9)',
      rows: [
        ['Średnio, gdy przesiadasz się zaraz po wysiadce', num(p.conn_w, 'min')],
        ['Mediana', num(p.conn_med, 'min')],
        ['Co dziesiąta przesiadka czeka dłużej niż', num(p.conn_p90, 'min')],
      ],
    })
  }
  if (has('gtt_lo', 'gtt_hi')) {
    sections.splice(2, 0, {
      title: 'Odczuwalny czas przesiadki (wagi z literatury, nie ranking)',
      rows: [['Pasmo, w minutach równoważnych jeździe', isNum(p.gtt_lo) && isNum(p.gtt_hi) ? `${nf(p.gtt_lo, 1)}–${nf(p.gtt_hi, 1)} min` : NO_DATA]],
    })
  }
  if (has('w6_hi', 'w6_lo')) {
    const obst = sections.find((s) => s.title === 'Przeszkody')
    obst.rows.push(['Bezpieczeństwo przejść (skala W6 z literatury)', isNum(p.w6_hi) && isNum(p.w6_lo) ? `${pct(p.w6_lo)}–${pct(p.w6_hi)}` : 'brak przejść z oceną'])
  }
  if (has('f10', 'f15')) {
    const sig = sections.find((s) => s.title === 'Znaczenie')
    sig.rows.push(['Przesiadki między liniami co najwyżej co 10 min', pct(p.f10)], ['… co najwyżej co 15 min', pct(p.f15)])
  }
  const notes = []
  if (p.use_ok && isNum(p.use)) notes.push(`Przesiada się tu ok. ${shareText(p.use)} podróży z próby tras (${nf(p.use_n, 0)} podróży).`)
  if (p.nodata) notes.push('Dla tego zespołu nie mamy rozkładów jazdy: składowych nie policzono.')
  if (p.flag) notes.push(p.flag)
  const date = timetableDate ? `Rozkład ${timetableDate}, ` : ''
  return {
    title: p.name || 'Zespół przystanków',
    modes: modesText(p.modes),
    sections,
    notes,
    footer: `${date}OSM 2026-11-22; własna miara projektu, każda składowa osobno`,
  }
}

/** DOM of the popup content. */
export function renderNodePopup(model, doc = document) {
  const el = (tag, cls, text) => {
    const e = doc.createElement(tag)
    if (cls) e.className = cls
    if (text != null) e.textContent = text
    return e
  }
  const root = el('div', 'node-popup')
  root.appendChild(el('h4', 'np-title', model.title))
  if (model.modes) root.appendChild(el('p', 'np-modes', model.modes))
  for (const s of model.sections) {
    const sec = el('section', 'np-section')
    sec.appendChild(el('h5', 'np-head', s.title))
    const dl = el('dl', 'np-rows')
    for (const [label, value] of s.rows) {
      const row = el('div', 'np-row')
      row.appendChild(el('dt', null, label))
      row.appendChild(el('dd', value === NO_DATA ? 'missing' : null, value))
      dl.appendChild(row)
    }
    sec.appendChild(dl)
    root.appendChild(sec)
  }
  for (const n of model.notes) root.appendChild(el('p', 'np-note', n))
  root.appendChild(el('p', 'np-foot', model.footer))
  return root
}

// ---- placement of a map popup (pure; MapView measures the DOM and calls this)
// Rects are {left, top, right, bottom} in the map container's pixels; `point` is the anchor point in the same pixels.

const TIP = 10   // MapLibre's popup tip: its size is part of the popup element on the anchor's side

const overlaps = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
const inside = (r, area) => r.left >= area.left - 0.5 && r.right <= area.right + 0.5 && r.top >= area.top - 0.5 && r.bottom <= area.bottom + 0.5

/** The rect a popup of `size` {w, h} (the element with its tip, measured with an anchor on top or bottom) takes for each MapLibre anchor. */
export function anchorRects(point, size, offset = 8) {
  const c = Math.round(offset / Math.SQRT2)
  const { x, y } = point
  const side = { w: size.w + TIP, h: size.h - TIP }   // the tip moves from the top/bottom edge to the side edge
  const box = (left, top, w, h) => ({ left, top, right: left + w, bottom: top + h })
  return {
    top: box(x - size.w / 2, y + offset, size.w, size.h),
    bottom: box(x - size.w / 2, y - offset - size.h, size.w, size.h),
    'top-left': box(x + c, y + c, size.w, size.h),
    'top-right': box(x - c - size.w, y + c, size.w, size.h),
    'bottom-left': box(x + c, y - c - size.h, size.w, size.h),
    'bottom-right': box(x - c - size.w, y - c - size.h, size.w, size.h),
    left: box(x + offset, y - side.h / 2, side.w, side.h),
    right: box(x - offset - side.w, y - side.h / 2, side.w, side.h),
  }
}

/** The pan [dx, dy] (px, as map.panBy takes it) that brings `r` into `area`: 0 where it already fits; a rect larger than the area is aligned to its top left. */
export function panToFit(r, area) {
  const shift = (lo, hi, aLo, aHi) => (hi - lo > aHi - aLo ? lo - aLo : lo < aLo ? lo - aLo : hi > aHi ? hi - aHi : 0)
  return [shift(r.left, r.right, area.left, area.right), shift(r.top, r.bottom, area.top, area.bottom)]
}

const ORDER = ['top', 'bottom', 'top-left', 'top-right', 'bottom-left', 'bottom-right', 'left', 'right']

/**
 * Where to open a popup: {anchor, rect, pan: [dx, dy]}. The first anchor (below the point, above it, then the corners and the
 * sides) whose popup lies wholly in `area` and clear of the `avoid` rects (the legend, the zoom buttons) is taken; failing
 * that, the first one that merely lies in `area`; failing that, the one that needs the smallest pan of the map to fit (`pan`
 * is that shift in px, [0, 0] otherwise; a popup larger than the area is aligned to its top left corner).
 */
export function placePopup({ point, size, area, avoid = [], offset = 8 }) {
  const rects = anchorRects(point, size, offset)
  for (const strict of [true, false]) {
    for (const a of ORDER) {
      const r = rects[a]
      if (inside(r, area) && (!strict || !avoid.some((o) => overlaps(r, o)))) return { anchor: a, rect: r, pan: [0, 0] }
    }
  }
  let best = null
  for (const a of ORDER) {
    const r = rects[a]
    const pan = panToFit(r, area)
    const cost = Math.abs(pan[0]) + Math.abs(pan[1])
    if (!best || cost < best.cost) best = { anchor: a, rect: r, pan, cost }
  }
  return { anchor: best.anchor, rect: best.rect, pan: best.pan }
}
