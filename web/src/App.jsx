import { useCallback, useEffect, useMemo, useState } from 'react'
import { AppMessage, AppShell, ErrorBoundary } from '@bartor-net/ui-kit'
import { loadCatalog, loadMetrics, isReady } from './data'
import { readHash, hashOf, resolveHash } from './urlState'
import MapView from './MapView'
import Sidebar from './Sidebar'
import Details from './Details'

const URL0 = readHash()

export default function App() {
  const [catalog, setCatalog] = useState(null)
  const [metrics, setMetrics] = useState({ generated: null, metrics: [] })
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([loadCatalog(), loadMetrics()])
      .then(([c, m]) => { setCatalog(c); setMetrics(m) })
      .catch((e) => setError(e.message || String(e)))
  }, [])

  if (error) {
    return (
      <AppMessage>
        Nie udało się wczytać danych: {error}. Odśwież stronę; jeśli problem wraca, katalog
        warstw (data/catalog.json) nie został opublikowany.
      </AppMessage>
    )
  }
  if (!catalog) return <AppMessage>Wczytywanie danych…</AppMessage>
  return <Loaded catalog={catalog} metrics={metrics} />
}

function Loaded({ catalog, metrics }) {
  // Layers on when nothing in the address says otherwise: the boundaries.
  const defaultLayers = useMemo(
    () => catalog.layers.filter((l) => isReady(l) && l.kind === 'boundary').map((l) => l.id),
    [catalog],
  )
  const start = useMemo(() => resolveHash(URL0, catalog, defaultLayers), [catalog, defaultLayers])

  const [selectedId, setSelectedId] = useState(start.agg)
  const [active, setActive] = useState(() => new Set(start.layers))
  const [sheetOpen, setSheetOpen] = useState(false)   // phones: the settings sheet
  // {bbox, animate, n}: a request to move the map; the address' own selection
  // is shown without animation
  const [fit, setFit] = useState(() => {
    const a = catalog.agglomerations.find((x) => x.id === start.agg)
    return a?.bbox ? { bbox: a.bbox, animate: false, n: 0 } : null
  })

  const selected = catalog.agglomerations.find((a) => a.id === selectedId) || null

  // picked in the list: fly there; clicked on the map: the view stays
  const pick = useCallback((id) => {
    setSelectedId(id)
    if (id) {
      setSheetOpen(false)   // two stacked sheets would leave no map to look at
      const a = catalog.agglomerations.find((x) => x.id === id)
      if (a?.bbox) setFit((f) => ({ bbox: a.bbox, animate: true, n: (f?.n || 0) + 1 }))
    }
  }, [catalog])
  const clickOnMap = useCallback((id) => {
    setSelectedId(id)
    setSheetOpen(false)
  }, [])
  const close = useCallback(() => setSelectedId(null), [])

  const setLayer = useCallback((id, on) => setActive((prev) => {
    const next = new Set(prev)
    if (on) next.add(id); else next.delete(id)
    return next
  }), [])

  // Keep the address in step, without adding a history entry per click.
  useEffect(() => {
    const h = hashOf({ agg: selectedId, layers: [...active] }, { layers: defaultLayers })
    if (h !== window.location.hash && !(h === '' && !window.location.hash)) {
      window.history.replaceState(null, '', h || window.location.pathname + window.location.search)
    }
  }, [selectedId, active, defaultLayers])

  return (
    <AppShell>
      <Sidebar
        catalog={catalog} metrics={metrics} selectedId={selectedId} onPick={pick}
        active={active} setLayer={setLayer} sheetOpen={sheetOpen} setSheetOpen={setSheetOpen}
      />
      <MapView
        catalog={catalog} active={active} selectedId={selectedId} onSelect={clickOnMap}
        fit={fit} detailsOpen={!!selected}
      />
      {selected && (
        <ErrorBoundary resetKey={selected.id} onClose={close}>
          <Details agglomeration={selected} metrics={metrics} onClose={close} />
        </ErrorBoundary>
      )}
    </AppShell>
  )
}
