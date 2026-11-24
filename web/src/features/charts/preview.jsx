// Dev-only preview of the charts feature (not part of the app build): open
// http://localhost:5173/src/features/charts/preview.html with the dev server running and data synced.
import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import '@bartor-net/ui-kit/base.css'
import '@bartor-net/ui-kit/styles.css'
import {
  AtLeastCurve, DotStrip, Dumbbell, ReachCurve, TimeOfDay, atLeastSeries, dotStripRows, dumbbellRows, floorOf,
  headwaySeries, layerMarks, loadCharts, reachSeries, timeOfDayRows,
} from './index'

function Preview() {
  const [c, setC] = useState(null)
  const [hotCity, setHotCity] = useState(null)
  const [pins, setPins] = useState([])
  const [hotClass, setHotClass] = useState(null)
  useEffect(() => { loadCharts({ base: '/data/' }).then(setC) }, [])
  if (!c) return <p style={{ color: '#ccc' }}>Ładowanie albo brak data/charts.json</p>
  const pin = (k) => setPins((p) => (p.includes(k) ? p.filter((x) => x !== k) : [...p, k]))
  const sel = 'wroclaw'
  const marks = layerMarks(c, 'transport_performance_30')
  return (
    <div className="grid">
      <div className="card"><AtLeastCurve series={atLeastSeries(c)} highlight={[sel]} marks={marks?.stops} floor={floorOf(c, 30)}
        hot={hotClass} onHot={setHotClass} hotSeries={hotCity} onHotSeries={setHotCity} pinnedSeries={pins} onPinSeries={pin}
        title="Transport performance 30 min: odsetek mieszkańców z co najmniej X (rdzeń)" /></div>
      <div className="card"><AtLeastCurve series={headwaySeries(c)} highlight={[sel, 'gzm']} unit="min" what="kursy"
        hotSeries={hotCity} onHotSeries={setHotCity} title="Kursy co najmniej co N min (rdzeń)" /></div>
      <div className="card"><ReachCurve series={reachSeries(c)} highlight={[sel]} hot={hotCity} onHot={setHotCity} pinned={pins} onPin={pin} /></div>
      <div className="card"><DotStrip {...dotStripRows(c, { measure: 'below_floor_30' })} better="low" selected={sel}
        hot={hotCity} onHot={setHotCity} pinned={pins} onPin={pin} /></div>
      <div className="card"><Dumbbell {...dumbbellRows(c, 'peak_evening_floor')} title="Poniżej progu 30 min: szczyt i wieczór"
        selected={sel} hot={hotCity} onHot={setHotCity} pinned={pins} onPin={pin} /></div>
      <div className="card"><Dumbbell {...dumbbellRows(c, 'core_uc')} title="Zasięg 30 min: rdzeń i centrum miejskie" selected={sel} /></div>
      <div className="card"><TimeOfDay rows={timeOfDayRows(c, { agg: 'gzm' })} title="GZM: zasięg o różnych porach (stosunek średnich)" /></div>
    </div>
  )
}
createRoot(document.getElementById('root')).render(<StrictMode><Preview /></StrictMode>)
