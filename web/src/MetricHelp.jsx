import { METRIC_INFO } from './metricInfo'
import { FEED_VARIANTS } from './metrics'
import { sourceModel } from './metricTable'

const pct = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 })

/**
 * The text behind a row's "?": how to read the number, how it was calculated, then where this row's numbers come
 * from. `entries` is [{key, row}]: the rows of the cells (cities or areas) with `nameOf(key)` for the names that
 * go with coverage and flags. A metric without an entry in METRIC_INFO has the source block only.
 */
export default function MetricHelp({ id, entries, nameOf, info = METRIC_INFO }) {
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
          <div className="kitx-src">
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
              <p key={f.text} className="kitx-warnline">{f.keys.length > 0 && <b>{f.keys.join(', ')}: </b>}{f.text}</p>
            ))}
          </div>
        </>
      )}
    </>
  )
}
