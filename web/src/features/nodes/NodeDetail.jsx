import { DataTable, Hint, Notes } from '@bartor-net/ui-kit'
import {
  NO_DATA, W6, W6_ORDER, bandText, matrixModel, minText, modeText, obstacleRows, summarySentence, topMovementTable,
} from './detailData'
import './nodeDetail.css'

/**
 * The detail card of a stop area, for the bottom dock (README.md in this folder has the wiring).
 *
 * Props
 *   node      decoded node (detailData.decodeNode), or null
 *   status    'loading' | 'ready' | 'none' | 'error' | 'idle' (useNodeDetail)
 *   name      the node's name from the map layer, shown while loading or when there is no detail
 *   hot       index of the lit movement (node.moves[i]) or null
 *   onHot     (moveIndex | null, pathIndex | null) => void: the pointer entered or left a movement in the matrix or
 *             the table; pathIndex is the movement's path in node.paths (-1 = same stop, null = no stored path).
 *             The page passes pathIndex on to detailLayers.setHotPath(map, pathIndex).
 *   timetableDate  e.g. "2026-11-25"
 */
export default function NodeDetail({ node, status, name, hot = null, onHot = () => {}, timetableDate }) {
  if (status === 'loading') return <div className="nd"><p className="nd-muted">Wczytywanie szczegółów węzła {name || ''}…</p></div>
  if (status === 'error') return <div className="nd"><p className="nd-muted">Nie udało się wczytać szczegółów węzła. Dane w dymku na mapie są aktualne.</p></div>
  if (status !== 'ready' || !node) {
    return (
      <div className="nd">
        <p className="nd-muted">
          {name ? `${name}: ` : ''}szczegóły są tylko dla zespołów z co najmniej 20 odjazdami na godzinę (6–20) w zasięgu
          rozkładów jazdy i z co najmniej jedną przesiadką między liniami.
        </p>
      </div>
    )
  }
  const enter = (m) => onHot(m.i, m.path ?? null)
  const leave = () => onHot(null, null)
  const s = node.sum
  const band = bandText(s)
  const obs = obstacleRows(node)
  return (
    <div className="nd">
      <p className="nd-lead">{summarySentence(node)}</p>
      <p className="nd-sub">
        {node.modes.map(modeText).join(', ')}; {minText(node.dep, '')} odjazdów na godzinę (6–20).
        {' '}Po rzeczywistym przyjeździe linii dowożącej czeka się średnio {minText(s.conn)} (mediana {minText(s.conn50)},
        {' '}9 na 10 przesiadek do {minText(s.conn90)}).
      </p>

      <section className="nd-block">
        <h3>Macierz przesiadek</h3>
        <Hint>
          Wiersze: linia, którą się przyjeżdża, i jej kierunek; kolumny: linia, do której się przesiada. W komórce
          dojście + mediana czekania po rzeczywistym przyjeździe, 7–9, w minutach. Najechanie pokazuje drogę na mapie.
        </Hint>
        <Matrix node={node} hot={hot} enter={enter} leave={leave} />
      </section>

      <section className="nd-block">
        <h3>Uogólniony czas przesiadki</h3>
        <p>
          {band
            ? <>W minutach równoważnych jeździe: <b>{band}</b>.</>
            : NO_DATA}
        </p>
        <Notes>
          <p>
            Dojście × 1,2–1,66 + czekanie × 1,47 + stała kara 5 / 13 / 18 min (wariant niski, środkowy, wysoki). Wagi z
            literatury: Wardman 1998 (dojście 1,66, czekanie 1,47), Ortelli i in. 2026 (dojście 1,21, kara 5–9 min),
            Jara-Díaz i in. 2022 (kara 13–18 min). To przeliczenie składowych, nie ocena węzła: nie służy do rankingu.
          </p>
        </Notes>
      </section>

      <section className="nd-block">
        <h3>Przeszkody</h3>
        <dl className="nd-rows">
          {obs.rows.map(([k, v]) => (
            <div key={k}><dt>{k}</dt><dd className={v === NO_DATA ? 'missing' : undefined}>{v}</dd></div>
          ))}
        </dl>
        <ul className="nd-w6" aria-label="Klasy przejść na mapie">
          {W6_ORDER.filter((k) => obs.counts[k] > 0).map((k) => (
            <li key={k}><span className="nd-dot" style={{ background: W6[k].color }} />{W6[k].label} ({W6[k].score}): {obs.counts[k]}</li>
          ))}
          {node.paths.some((p) => p.steps.length) && <li><span className="nd-dot nd-steps" />początek schodów</li>}
        </ul>
      </section>

      <section className="nd-block">
        <h3>Najczęstsze przesiadki</h3>
        <MovesTable node={node} hot={hot} enter={enter} leave={leave} />
        <p className="nd-foot">
          Rozkład {timetableDate || ''}, sieć piesza OSM 2026-11-22, 5 km/h. Kursy = przyjazdy linii A w jej kierunku ×
          odjazdy linii B w jej kierunku (6–20): waga ruchu, nie liczba pasażerów. Miara własna, składowe osobno.
        </p>
      </section>
    </div>
  )
}

function Matrix({ node, hot, enter, leave }) {
  const { rows, cols, cells } = matrixModel(node)
  if (!rows.length || !cols.length) return <p className="nd-muted">{NO_DATA}</p>
  return (
    <div className="nd-matrix-wrap">
      <table className="nd-matrix">
        <thead>
          <tr>
            <th scope="col" className="nd-corner">z ↓ / na →</th>
            {cols.map((c) => <th key={c.i} scope="col" title={`${c.label} (${c.n} odjazdów 6–20)`}><span>{c.label}</span></th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={r.i}>
              <th scope="row" title={`${r.label} (${r.n} przyjazdów 6–20)`}>{r.label}</th>
              {cells[ri].map((c, ci) => {
                if (c.kind !== 'move') {
                  return <td key={cols[ci].i} className="nd-empty" title={c.kind === 'same' ? 'ta sama linia' : 'bez przesiadki w tym kierunku'}>·</td>
                }
                const m = c.move
                const label = c.parts ? `${minText(c.parts.walk, '')} + ${minText(c.parts.wait, '')}` : NO_DATA
                return (
                  <td
                    key={cols[ci].i} className={hot === m.i ? 'hot' : undefined}
                    style={c.color ? { boxShadow: `inset 3px 0 0 ${c.color}` } : undefined}
                    title={`${m.from.label} → ${m.to.label}: dojście ${minText(m.walk)}, czekanie na przesiadkę ${minText(m.conn)} (P90 ${minText(m.conn90)})`}
                    onMouseEnter={() => enter(m)} onMouseLeave={leave} onFocus={() => enter(m)} onBlur={leave} tabIndex={0}
                  >
                    {c.parts ? <><b>{minText(c.parts.total, '')}</b><small>{label}</small></> : <span className="missing">{NO_DATA}</span>}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MovesTable({ node, hot, enter, leave }) {
  const { columns, rows } = topMovementTable(node)
  if (!rows.length) return <p className="nd-muted">{NO_DATA}</p>
  // the kit's table lights columns, not rows: the label and each cell carry the hover of their movement
  const wrap = (m, content) => (
    <span className={`nd-cell${hot === m.i ? ' hot' : ''}`} onMouseEnter={() => enter(m)} onMouseLeave={leave}>{content}</span>
  )
  const kitRows = rows.map(({ move, ...r }) => ({
    ...r,
    label: wrap(move, r.label),
    name: r.label,
    cells: r.cells.map((c) => (c ? { ...c, content: wrap(move, c.content) } : c)),
  }))
  return (
    <DataTable
      caption="Najczęstsze przesiadki w węźle" sortBy="column" labelHead="Z linii" columns={columns} rows={kitRows}
      maxHeight="min(22rem, 50dvh)"
    />
  )
}
