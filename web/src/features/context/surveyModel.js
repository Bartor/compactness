// Pure logic of the survey-context block: results/web/survey_context.json (pipeline/survey_context.py) -> what the
// block shows for one agglomeration. Every number in the file is {v, src, loc[, note]}; null means "not published".
import { DATA_BASE_URL } from '../../config'

export const SURVEY_FILE = 'survey_context.json'

export const MODE_ORDER = ['walk', 'bike', 'pt', 'car', 'other']
export const MODE_LABEL = { walk: 'pieszo', bike: 'rower', pt: 'komunikacja zbiorowa', car: 'samochód', other: 'inne' }
/** Colours for the dark panels; public transport takes the site accent family. */
export const MODE_COLOR = { walk: '#C9B98F', bike: '#8FC98F', pt: '#6C9BE0', car: '#C98A8A', other: '#8A909C' }
export const STATUS_LABEL = {
  published: null, partial: 'tylko częściowe wyniki', in_progress: 'badanie w toku', none: 'brak badania',
}

const val = (x) => (x && typeof x === 'object' && 'v' in x ? x.v : null)

/** The survey file, or null when it is absent (the block then says nothing at all). */
export async function loadSurveyContext({ base = DATA_BASE_URL, fetchImpl = globalThis.fetch } = {}) {
  try {
    const res = await fetchImpl(base + SURVEY_FILE)
    if (!res.ok) return null
    const d = await res.json()
    return d && d.agglomerations ? d : null
  } catch {
    return null
  }
}

/** Polish number with a comma: 21.6 -> "21,6". */
export const pl = (x) => (x === null || x === undefined ? '–' : String(x).replace('.', ','))

/**
 * Segments of one stacked bar: [{mode, label, value, color, note}], published modes only, in MODE_ORDER.
 * `rest` is 100 minus their sum when that is at least 0.5 (shown as "nie podano", never as a mode).
 */
export function barSegments(split) {
  if (!split) return { segments: [], rest: null }
  const segments = MODE_ORDER.filter((m) => val(split[m]) !== null).map((m) => ({
    mode: m, label: MODE_LABEL[m], value: val(split[m]), color: MODE_COLOR[m], note: split[m].note || null,
  }))
  const sum = segments.reduce((s, x) => s + x.value, 0)
  const rest = 100 - sum >= 0.5 ? Math.round((100 - sum) * 10) / 10 : null
  return { segments, rest }
}

/** Source link of a value or of the record: {title, url} or null. */
export function sourceOf(file, key) {
  const s = key && file?.sources?.[key]
  return s ? { title: s.title, url: s.url, primary: !!s.primary } : null
}

/**
 * What the block shows for one agglomeration:
 * {status, statusLabel, title, year, bars: [{label, segments, rest}], base, comparability, facts, sources, upcoming}
 * or null when the file has no record for it.
 */
export function surveyView(file, agg) {
  const r = file?.agglomerations?.[agg]
  if (!r) return null
  const srcKeys = new Set()
  const add = (x) => { if (x && x.src) srcKeys.add(x.src) }
  const bars = []
  if (r.modal_split) {
    Object.values(r.modal_split).forEach(add)
    bars.push({ label: null, ...barSegments(r.modal_split) })
  }
  for (const p of r.partial || []) {
    MODE_ORDER.forEach((m) => add(p[m]))
    bars.push({ label: p.label, ...barSegments(p) })
  }
  const facts = []
  if (val(r.avg_trip_min) !== null) {
    add(r.avg_trip_min)
    facts.push(`średni czas podróży ${pl(val(r.avg_trip_min))} min${r.avg_trip_min.note ? ` (${r.avg_trip_min.note})` : ''}`)
  }
  if (val(r.avg_trip_min_pt) !== null) {
    add(r.avg_trip_min_pt)
    facts.push(`komunikacją zbiorową średnio ${pl(val(r.avg_trip_min_pt))} min`)
  }
  if (val(r.pt_transfer_share) !== null) {
    add(r.pt_transfer_share)
    facts.push(`${pl(val(r.pt_transfer_share))} % podróży komunikacją z przesiadką`)
  }
  add(r.year)
  if (r.upcoming) srcKeys.add(r.upcoming.src)
  if (r.none_src) srcKeys.add(r.none_src.src)
  return {
    status: r.status,
    statusLabel: STATUS_LABEL[r.status] ?? null,
    title: r.survey,
    year: val(r.year),
    bars,
    base: r.base || null,
    splitNote: r.modal_split_note || null,
    comparability: r.comparability || null,
    facts,
    upcoming: r.upcoming ? { text: r.upcoming.text, source: sourceOf(file, r.upcoming.src) } : null,
    sources: [...srcKeys].sort().map((k) => sourceOf(file, k)).filter(Boolean),
  }
}
