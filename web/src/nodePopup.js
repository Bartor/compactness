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

export const SUM_LABEL = 'Typowa przesiadka 7–9 (średnia ważona liczbą kursów)'

/**
 * {title, modes, sections: [{title, rows: [[label, value]]}], notes: [text], footer}.
 * Properties are those of results/web/transfer_nodes.geojson (shares are fractions).
 */
export function nodePopupModel(p, timetableDate) {
  const excl = isNum(p.pairs_excl) && p.pairs_excl > 0 ? ` (pominięto równoległych: ${nf(p.pairs_excl, 0)})` : ''
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
        ['Z kierunkami, 90. percentyl', num(p.walk_dir_p90, 'min')],
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
  const notes = []
  if (p.nodata) notes.push('Zespół leży poza pokryciem rozkładów GTFS: składowych nie policzono.')
  if (p.flag) notes.push(p.flag)
  const date = timetableDate ? `Rozkład ${timetableDate}, ` : ''
  return {
    title: p.name || 'Zespół przystanków',
    modes: modesText(p.modes),
    sections,
    notes,
    footer: `${date}OSM 2026-11-22; miara własna, składowe osobno`,
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
