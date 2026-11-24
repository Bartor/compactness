import { METRIC_INFO } from './metricInfo'
import { FEED_VARIANTS } from './metrics'
import { sourceModel } from './metricTable'
import { firstSentence } from './helpText'

const pct = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 })

/**
 * The text behind a row's "?": how to read the number, how it was calculated, then where this row's numbers come
 * from. `entries` is [{key, row}]: the rows of the cells (cities or areas) with `nameOf(key)` for the names that
 * go with coverage and flags. A metric without an entry in METRIC_INFO has the source block only. `onOpen`, when
 * given, adds the link to the metric's own page at the end.
 */
export default function MetricHelp({ id, entries, nameOf, info = METRIC_INFO, onOpen }) {
  const i = info[id]
  const s = sourceModel(entries, { feedNames: FEED_VARIANTS, nameOf })
  const hasSource = s.source || s.dates.length || s.feed || s.coverage.length || s.flags.length
  return (
    <>
      {i?.read?.length > 0 && (
        <>
          <h5>Jak czytać</h5>
          {i.read.map((p) => <p key={p}>{p}</p>)}
        </>
      )}
      {i?.method?.length > 0 && (
        <>
          <h5>Jak policzono</h5>
          {i.method.map((p) => <p key={p}>{p}</p>)}
        </>
      )}
      {hasSource && (
        <>
          <h5>Źródło tych liczb</h5>
          <div className="help-src">
            {s.source && <p>{s.source}</p>}
            {(s.dates.length > 0 || s.feed) && (
              <p>{[...s.dates, s.feed].filter(Boolean).join(' · ')}</p>
            )}
            {s.coverage.length > 0 && (
              <p>
                <b>Pokrycie danymi o rozkładach:</b>{' '}
                {s.coverage.map((c) => `${c.key} ${pct.format(c.share * 100)} %`).join(', ')}
              </p>
            )}
            {s.flags.map((f) => (
              <p key={f.text} className="help-warnline">{f.keys.length > 0 && <b>{f.keys.join(', ')}: </b>}{f.text}</p>
            ))}
          </div>
        </>
      )}
      {onOpen && (
        <p className="metric-open-wrap">
          <button type="button" className="metric-open" onClick={onOpen}>Otwórz stronę miary</button>
        </p>
      )}
    </>
  )
}

/**
 * The one help pattern of the tables: the first sentence of "jak czytać", which way is better, and a link to the whole
 * text on the metric's page. Without an entry in METRIC_INFO it says so and still links to the page.
 */
export function ShortHelp({ id, info = METRIC_INFO, onOpen }) {
  const i = info[id]
  const lead = (i?.read || []).find((p) => !p.startsWith('Niepewność'))
  const dir = i?.better === 'higher' ? 'wyżej = lepiej' : i?.better === 'lower' ? 'niżej = lepiej' : null
  return (
    <>
      <p>{lead ? firstSentence(lead) : 'Ta miara nie ma jeszcze opisu.'}</p>
      {dir && <p className="help-dir">{dir}</p>}
      {onOpen && (
        <p className="metric-open-wrap">
          <button type="button" className="metric-open" onClick={onOpen}>więcej na stronie miary</button>
        </p>
      )}
    </>
  )
}
