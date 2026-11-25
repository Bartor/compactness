// A small card for the "skąd dojadę" mode: which precomputed origin is shown, how far it is from the click, and
// how many residents can be reached in each band in the morning, in the evening and on foot.
import { KIND_LABEL, SCENARIO_LABEL, cardRows, formatDistance, formatResidents } from './isoModel'
import { bandLegend } from './isoLayers'
import './isochrones.css'

/**
 * Props
 *   file       the loaded isochrone file (useIsochroneMode().file); null shows the status line only
 *   status     'off' | 'loading' | 'ready' | 'missing'
 *   origin     the picked origin {id, name, kind, lon, lat} or null (then a hint to click on the map)
 *   distanceM  metres from the click to the origin
 *   scenario   'am' | 'evening': which one the map shows
 *   onScenario (s) => void
 *   onClose    () => void, optional: leaves the mode
 */
export default function IsochroneCard({ file, status, origin, distanceM, scenario = 'am', onScenario, onClose }) {
  let body
  if (status === 'loading') body = <p className="iso-hint">Wczytywanie zasięgów…</p>
  else if (status === 'missing' || !file) body = <p className="iso-hint">Dla tego miasta nie ma wyliczonych zasięgów.</p>
  else if (!origin) body = <p className="iso-hint">Kliknij na mapie w obrębie miasta: pokażemy, dokąd dojedziesz z najbliższego wyliczonego punktu.</p>
  else {
    const rows = cardRows(file, origin.id)
    body = (
      <>
        <p className="iso-origin">
          <strong>{origin.name}</strong> <span className="iso-kind">{KIND_LABEL[origin.kind] || ''}</span>
          {distanceM > 0 && <span className="iso-dist"> · {formatDistance(distanceM)} od kliknięcia</span>}
        </p>
        <div className="iso-switch" role="radiogroup" aria-label="Pora dnia na mapie">
          {['am', 'evening'].map((s) => (
            <button
              key={s} type="button" role="radio" aria-checked={scenario === s}
              className={scenario === s ? 'on' : ''} onClick={() => onScenario?.(s)}
            >{SCENARIO_LABEL[s]}</button>
          ))}
        </div>
        <table className="iso-table">
          <caption>Mieszkańcy, do których można dojechać</caption>
          <thead>
            <tr><th scope="col">czas</th><th scope="col">rano</th><th scope="col">wieczorem</th><th scope="col">pieszo</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.minutes}>
                <th scope="row">
                  <span className="iso-swatch" style={{ background: bandLegend()[i]?.color }} aria-hidden="true" />
                  {r.label}
                </th>
                <td>{formatResidents(r.am)}</td>
                <td>{formatResidents(r.evening)}</td>
                <td>{formatResidents(r.walk)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="iso-note">
          Komunikacja z dojściem pieszym; typowy czas (mediana) przy wyjściu w dowolnej minucie, środa {file.day}.
          Czasy z rozkładu jazdy, nie rzeczywiste. Linia przerywana: zasięg pieszo. Pokazany jest najbliższy wyliczony punkt, a nie miejsce
          kliknięcia.
        </p>
      </>
    )
  }
  return (
    <section className="iso-card" aria-label="Dokąd dojadę stąd">
      <header>
        <h3>Dokąd dojadę stąd</h3>
        {onClose && <button type="button" className="iso-close" onClick={onClose} aria-label="Zamknij „Dokąd dojadę stąd”">×</button>}
      </header>
      {body}
    </section>
  )
}
