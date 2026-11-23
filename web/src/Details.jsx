import { DetailsPanel, Hint, TextTable, Warn } from '@bartor-net/ui-kit'
import { formatValue, groupMetrics, isSecondary, metricNotes } from './metrics'
import { ACCENT } from './config'

// Rows of tier "table" (fine in a table, not for a graphic) are shown dimmer and lighter.
const SECONDARY = { opacity: 0.72, fontWeight: 400 }

function Row(m) {
  const v = formatValue(m)
  const notes = metricNotes(m)
  const style = isSecondary(m) ? SECONDARY : undefined
  return [
    <span style={style}>{m.label || m.metric}{notes && <small>{notes}</small>}</span>,
    <span style={style}>
      <span className={v.missing ? 'metric-value missing' : 'metric-value'}>{v.text}</span>
      {m.flag && <small className="metric-flag">{m.flag}</small>}
    </span>,
  ]
}

/** Metrics of the selected agglomeration, grouped by domain. */
export default function Details({ agglomeration, metrics, onClose }) {
  const groups = groupMetrics(metrics.metrics, agglomeration.id)
  return (
    <DetailsPanel
      pill={agglomeration.phase != null ? `Etap ${agglomeration.phase}` : undefined}
      title={agglomeration.name} color={ACCENT} onClose={onClose}
    >
      {agglomeration.note && <Warn>{agglomeration.note}</Warn>}
      {groups.length === 0 && (
        <Hint>
          {metrics.metrics.length === 0
            ? 'Miary pojawią się po przeliczeniu.'
            : 'Dla tej aglomeracji nie ma jeszcze przeliczonych miar.'}
        </Hint>
      )}
      {groups.map((g) => (
        <section key={g.domain} className="metric-group">
          <h4>{g.title}</h4>
          <TextTable head={['Miara', 'Wartość']} rows={g.rows.map(Row)} />
        </section>
      ))}
      {groups.length > 0 && (
        <Hint>Wartość „brak danych” oznacza, że miary nie da się policzyć, a nie że wynosi zero.</Hint>
      )}
    </DetailsPanel>
  )
}
