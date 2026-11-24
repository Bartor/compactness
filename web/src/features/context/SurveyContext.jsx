// A compact block for the city view: how residents travel according to the latest household travel survey, with the
// year, the source and one plain sentence on why cities cannot be compared one to one.
import { MODE_LABEL, MODE_ORDER, MODE_COLOR, pl, surveyView } from './surveyModel'
import './context.css'

function Bar({ label, segments, rest }) {
  const aria = segments.map((s) => `${s.label} ${pl(s.value)} %`).join(', ') + (rest ? `, nie podano ${pl(rest)} %` : '')
  return (
    <figure className="sc-bar-wrap">
      {label && <figcaption className="sc-bar-label">{label}</figcaption>}
      <div className="sc-bar" role="img" aria-label={aria}>
        {segments.map((s) => (
          <span
            key={s.mode} className="sc-seg" title={`${s.label}: ${pl(s.value)} %${s.note ? ` (${s.note})` : ''}`}
            style={{ width: `${s.value}%`, background: s.color }}
          >{s.value >= 9 ? `${pl(s.value)}` : ''}</span>
        ))}
        {rest && <span className="sc-seg sc-rest" title={`nie podano: ${pl(rest)} %`} style={{ width: `${rest}%` }} />}
      </div>
    </figure>
  )
}

/**
 * Props
 *   data  the loaded survey_context.json (loadSurveyContext()); null renders nothing
 *   agg   agglomeration id ('warszawa', ...)
 */
export default function SurveyContext({ data, agg }) {
  const v = surveyView(data, agg)
  if (!data) return null
  // a city the file does not know (no survey for it): say so, do not leave a gap
  if (!v) {
    return (
      <section className="sc" aria-label="Jak mieszkańcy podróżują: badanie ruchu">
        <h3 className="sc-title">Jak mieszkańcy podróżują: badanie ruchu</h3>
        <p className="sc-none"><strong>brak badania</strong></p>
      </section>
    )
  }
  const shown = new Set(v.bars.flatMap((b) => b.segments.map((s) => s.mode)))
  const hasRest = v.bars.some((b) => b.rest)
  return (
    <section className="sc" aria-label="Jak mieszkańcy podróżują: badanie ruchu">
      <h3 className="sc-title">Jak mieszkańcy podróżują: badanie ruchu</h3>
      {v.status === 'none' || v.status === 'in_progress' ? (
        <p className="sc-none"><strong>{v.statusLabel === 'badanie w toku' ? 'brak badania (badanie w toku)' : 'brak badania'}</strong></p>
      ) : (
        <p className="sc-meta">
          {v.title}{v.year ? `, ${v.year}` : ''}{v.statusLabel ? ` · ${v.statusLabel}` : ''}
        </p>
      )}
      {v.bars.map((b, i) => <Bar key={i} {...b} />)}
      {v.bars.length > 0 && (
        <ul className="sc-legend">
          {MODE_ORDER.filter((m) => shown.has(m)).map((m) => (
            <li key={m}><span className="sc-dot" style={{ background: MODE_COLOR[m] }} aria-hidden="true" />{MODE_LABEL[m]}</li>
          ))}
          {hasRest && <li><span className="sc-dot sc-rest" aria-hidden="true" />nie podano</li>}
        </ul>
      )}
      {v.base && <p className="sc-small">Udziały w %: {v.base}.</p>}
      {v.splitNote && <p className="sc-small">{v.splitNote}</p>}
      {v.facts.length > 0 && <p className="sc-small">{v.facts.join('; ')}.</p>}
      {v.comparability && <p className="sc-comp">{v.comparability}</p>}
      {v.upcoming && <p className="sc-small">{v.upcoming.text}</p>}
      {v.sources.length > 0 && (
        <p className="sc-src">
          Źródło:{' '}
          {v.sources.map((s, i) => (
            <span key={s.url}>
              {i > 0 && '; '}
              <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a>
            </span>
          ))}
        </p>
      )}
    </section>
  )
}
