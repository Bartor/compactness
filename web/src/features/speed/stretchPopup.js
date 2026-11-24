// The popup of a stretch (or of a metro / rail line): pure model from the feature's properties, and a DOM builder in
// the style of nodePopup.js (no innerHTML: names come from data). Every speed is scheduled, not measured.
import {
  CLASS_COLORS, MODE_PL, POPUP_BANDS, SCHEDULED, bandText, classOf, linesOf, props, roundingInterval,
} from './speedModel'

export const NO_DATA = 'brak danych'
export const TAF_CAVEAT = 'Model, nie pomiar: czas rozkładowy minus czas prostego modelu jazdy (rozpędzanie, limit '
  + 'prędkości, hamowanie, postój 20 s). Zawiera sygnalizację, ograniczenia prędkości, wymianę pasażerów i rezerwy '
  + 'rozkładu. Przedział: postój 10–30 s i limit 40–70 km/h tam, gdzie OSM nie podaje limitu.'
export const FASTER_TEXT = 'Rozkład jest tu szybszy niż model jazdy swobodnej (zwykle szybkie torowisko wydzielone z limitem '
  + 'wyższym niż przyjęte 50 km/h); czasu ponad jazdę swobodną nie podajemy.'

const isNum = (v) => typeof v === 'number' && Number.isFinite(v)
const nf = (v, d) => new Intl.NumberFormat('pl-PL', { maximumFractionDigits: d, minimumFractionDigits: 0, useGrouping: 'always' }).format(v)
export const num = (v, unit = '', d = 1) => (isNum(v) ? `${nf(v, d)}${unit ? ` ${unit}` : ''}` : NO_DATA)
export const pct = (v) => (isNum(v) ? `${nf(v * 100, 0)} %` : NO_DATA)

/** "17,2 km/h (±1 min: 15,8–18,9)" */
export function speedText(len, v) {
  if (!isNum(v)) return NO_DATA
  const r = roundingInterval(len, v)
  if (!r) return `${nf(v, 1)} km/h`
  const hi = r.hi == null ? 'bez górnej granicy' : nf(r.hi, 1)
  return `${nf(v, 1)} km/h (±1 min: ${nf(r.lo, 1)}–${hi})`
}

/** "45 s/km (30–70)" or the faster-than-model sentence or "brak danych". */
export function tafText(p, band) {
  const k = props(band)
  if (p[k.fm]) return 'rozkład szybszy niż model'
  if (!isNum(p[k.a])) return NO_DATA
  const range = isNum(p[k.al]) && isNum(p[k.ah]) ? ` (${nf(p[k.al], 0)}–${nf(p[k.ah], 0)})` : ''
  return `${nf(p[k.a], 0)} s/km${range}`
}

/** Bars of the speed per band: [{key, label, value, cls, color, width}], width 0..1 of the row's maximum. */
export function bandBars(p) {
  const vals = POPUP_BANDS.map((b) => p[props(b.key).v])
  const max = Math.max(0, ...vals.filter(isNum))
  return POPUP_BANDS.map((b, i) => {
    const v = vals[i]
    const cls = classOf(v)
    return { key: b.key, label: bandText(b.key), value: isNum(v) ? v : null, cls,
      color: cls >= 0 ? CLASS_COLORS[cls] : null, width: isNum(v) && max > 0 ? v / max : 0 }
  })
}

/**
 * {title, subtitle, bars, sections: [{title, rows: [[label, value]]}], notes, footer} for a feature of
 * trams.geojson, bus_<agg>.geojson or rail.geojson, in the selected band.
 */
export function stretchPopupModel(p, band, timetableDates = null) {
  const isLine = p.m === 'rail' || p.m === 'metro'
  const lines = linesOf(p.ln)
  const k = props(band)
  const main = [
    [`Prędkość, ${bandText(band)}`, isLine ? num(p[k.v], 'km/h') : speedText(p.len, p[k.v])],
    ['Kursy na godzinę', num(p[k.t])],
  ]
  if (!isLine) {
    main.push(['Długość', num(p.len, 'm', 0)])
    main.push(['Przystanki', isNum(p.ns) ? nf(p.ns, 0) : NO_DATA])
  }
  const sections = [{ title: 'W wybranym paśmie', rows: main }]
  const notes = []
  if (p.m === 'tram') {
    sections.push({
      title: 'Czas ponad jazdę swobodną (model)',
      rows: [[`${bandText(band)}, środek (przedział)`, tafText(p, band)]],
    })
    sections.push({
      title: 'Tor (OSM)',
      rows: [
        ['W jezdni (dolne oszacowanie)', pct(p.st)],
        ['Skrzyżowania z drogą (z sygnalizacją)', isNum(p.x) ? `${nf(p.x, 0)} (${isNum(p.xs) ? nf(p.xs, 0) : NO_DATA})` : NO_DATA],
        ['Przejścia poza skrzyżowaniami', num(p.xp, '', 0)],
        ['Rozjazdy', num(p.sw, '', 0)],
      ],
    })
    if (p[k.fm]) notes.push(FASTER_TEXT)
    notes.push(TAF_CAVEAT)
  }
  if (p.short) notes.push('Odcinek krótszy niż 5 minut: zaokrąglenie rozkładu do pełnych minut mocno zmienia prędkość.')
  if (p.straight) notes.push('Geometria głównie w linii prostej między przystankami: długość i prędkość są zaniżone.')
  if (p.unoff) notes.push('Feed nieoficjalny, niezweryfikowany.')
  const dates = timetableDates ? `środa ${timetableDates.weekday}, sobota ${timetableDates.saturday}; ` : ''
  return {
    title: p.name || (isLine ? `Linia ${p.line}` : 'Odcinek'),
    subtitle: [MODE_PL[p.m] || p.m, lines.length ? `linie: ${lines.join(', ')}` : null].filter(Boolean).join(' · '),
    stops: p.stops || null,
    bars: bandBars(p),
    sections,
    notes,
    footer: `${dates}${SCHEDULED}`,
  }
}

/** DOM of the popup content. */
export function renderStretchPopup(model, doc = document) {
  const el = (tag, cls, text) => {
    const e = doc.createElement(tag)
    if (cls) e.className = cls
    if (text != null) e.textContent = text
    return e
  }
  const root = el('div', 'node-popup speed-popup')
  root.appendChild(el('h4', 'np-title', model.title))
  if (model.subtitle) root.appendChild(el('p', 'np-modes', model.subtitle))
  if (model.stops) root.appendChild(el('p', 'sp-stops', model.stops))
  const bars = el('div', 'sp-bars')
  bars.setAttribute('role', 'img')
  bars.setAttribute('aria-label', model.bars.map((b) => `${b.label}: ${b.value == null ? NO_DATA : `${nf(b.value, 1)} km/h`}`).join('; '))
  for (const b of model.bars) {
    const bar = el('span', b.value == null ? 'sp-bar missing' : 'sp-bar')
    bar.title = `${b.label}: ${b.value == null ? NO_DATA : `${nf(b.value, 1)} km/h`}`
    const fill = el('i', null)
    fill.style.height = `${Math.round(b.width * 100)}%`
    if (b.color) fill.style.background = b.color
    bar.appendChild(fill)
    bars.appendChild(bar)
  }
  root.appendChild(bars)
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
