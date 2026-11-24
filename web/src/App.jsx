import { useCallback, useEffect, useMemo, useState } from 'react'
import { AppMessage, AppShell, DetailsPanel, ErrorBoundary, Modal } from '@bartor-net/ui-kit'
import { loadAttributions, loadCatalog, loadClassShares, loadMetrics } from './data'
import {
  activeIds, chooseOverlay, revealLayer, setOverlayOn, setValue, setVariant,
} from './layerControl'
import { readHash, hashOfView, resolveHash } from './urlState'
import { sharesFor } from './classShares'
import { allCities, indexMetrics, transportCities } from './metricTable'
import { useFocuses } from './useFocuses'
import { useCityNodes } from './useCityNodes'
import { usePhone } from './usePhone'
import MapView from './MapView'
import Sidebar from './Sidebar'
import CityPanel from './CityPanel'
import Compare from './Compare'
import About from './About'
import Dock from './kitx/Dock'

const URL0 = readHash()

export default function App() {
  const [catalog, setCatalog] = useState(null)
  const [metrics, setMetrics] = useState({ generated: null, metrics: [] })
  const [attributions, setAttributions] = useState({ gtfs_feeds: [] })
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([loadCatalog(), loadMetrics(), loadAttributions()])
      .then(([c, m, a]) => { setCatalog(c); setMetrics(m); setAttributions(a) })
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
  return <Loaded catalog={catalog} metrics={metrics} attributions={attributions} />
}

function Loaded({ catalog, metrics, attributions }) {
  const layers = catalog.layers
  const start = useMemo(() => resolveHash(URL0, catalog), [catalog])

  const [selectedId, setSelectedId] = useState(start.agg)
  // which layers are on: the state of layerControl.js, and the plain set of ids drawn from it
  const [view, setView] = useState(start.state)
  const active = useMemo(() => activeIds(view, layers), [view, layers])
  const focus = useFocuses(active)
  const phone = usePhone()
  const [sheetOpen, setSheetOpen] = useState(false)   // phones: the settings sheet
  // {bbox, animate, n}: a request to move the map; the address' own selection
  // is shown without animation
  const [fit, setFit] = useState(() => {
    const a = catalog.agglomerations.find((x) => x.id === start.agg)
    return a?.bbox ? { bbox: a.bbox, animate: false, n: 0 } : null
  })

  // the city lit on the map and in the tables: one state for both
  const [hot, setHot] = useState(null)
  const [area, setArea] = useState('core')           // the area the comparison refers to
  const [compareOpen, setCompareOpen] = useState(true)   // desktop: the comparison in the details slot
  const [compareSheet, setCompareSheet] = useState(false)   // phones: the comparison as a modal
  const [about, setAbout] = useState(null)           // null, or {limits}: the "O danych" modal
  const [nodeRequest, setNodeRequest] = useState(null)   // {layer, props, coordinates, n}
  const [classShares, setClassShares] = useState({})
  useEffect(() => { loadClassShares().then(setClassShares) }, [])

  const index = useMemo(() => indexMetrics(metrics.metrics), [metrics])
  const known = useMemo(() => catalog.agglomerations.map((a) => a.id), [catalog])
  const names = useMemo(() => Object.fromEntries(catalog.agglomerations.map((a) => [a.id, a.name])), [catalog])
  const cities = useMemo(() => transportCities(index, known), [index, known])
  const everyCity = useMemo(() => allCities(index, known), [index, known])

  const selected = catalog.agglomerations.find((a) => a.id === selectedId) || null
  const sharesOf = useCallback((layerId) => sharesFor(classShares, layerId, selectedId), [classShares, selectedId])

  // picked in the list: fly there; clicked on the map: the view stays, unless
  // the click came from the whole-country view
  const pick = useCallback((id) => {
    setSelectedId(id)
    setHot(null)
    if (id) {
      setSheetOpen(false)   // two stacked sheets would leave no map to look at
      setCompareSheet(false)
      const a = catalog.agglomerations.find((x) => x.id === id)
      if (a?.bbox) setFit((f) => ({ bbox: a.bbox, animate: true, n: (f?.n || 0) + 1 }))
    }
  }, [catalog])
  const clickOnMap = useCallback((id, far) => {
    if (far) return pick(id)   // clicked from far out: go there
    setSelectedId(id)
    setSheetOpen(false)
  }, [pick])
  const close = useCallback(() => { setSelectedId(null); setHot(null) }, [])
  const openCompare = useCallback(() => {
    if (phone) {
      setSheetOpen(false)
      setCompareSheet(true)
    } else {
      setCompareOpen(true)
      setSelectedId(null)
    }
  }, [phone])

  // layer controls
  const onValue = useCallback((id) => setView((v) => setValue(v, id, layers)), [layers])
  const onOverlayOn = useCallback((kind, on) => setView((v) => setOverlayOn(v, kind, on)), [])
  const onOverlayLayer = useCallback((kind, id) => setView((v) => chooseOverlay(v, kind, id, layers)), [layers])
  const onVariant = useCallback((layer, key) => setView((v) => setVariant(v, layer, key)), [])
  // "na mapie" in a table: show that layer, whichever kind it is
  const showLayer = useCallback((id) => {
    setView((v) => revealLayer(v, layers, id))
    if (phone) setCompareSheet(false)
  }, [layers, phone])

  // the busiest stop areas of the selected city: from the points layer chosen for the nodes overlay
  const pointsGroup = view.overlays.points
  const pointsLayer = pointsGroup ? layers.find((l) => l.id === pointsGroup.layer && l.status === 'ready') : null
  const nodes = useCityNodes(pointsLayer, selectedId)
  const showNode = useCallback((layer, n) => {
    setView((v) => revealLayer(v, layers, layer.id))
    setNodeRequest((r) => ({ layer, props: n.props, coordinates: n.coordinates, n: (r?.n || 0) + 1 }))
  }, [layers])

  // Keep the address in step, without adding a history entry per click.
  useEffect(() => {
    const h = hashOfView(selectedId, view, layers)
    if (h !== window.location.hash && !(h === '' && !window.location.hash)) {
      window.history.replaceState(null, '', h || window.location.pathname + window.location.search)
    }
  }, [selectedId, view, layers])

  const compare = (
    <Compare
      index={index} cities={cities} everyCity={everyCity} names={names}
      area={area} setArea={setArea} layers={layers} onShowLayer={showLayer}
      onPickCity={pick} hot={hot} setHot={setHot}
      onOpenLimits={() => setAbout({ limits: true })}
    />
  )

  return (
    <AppShell>
      <Sidebar
        catalog={catalog} metrics={metrics} selectedId={selectedId} onPick={pick}
        view={view} active={active} onValue={onValue} onOverlayOn={onOverlayOn}
        onOverlayLayer={onOverlayLayer} onVariant={onVariant} focus={focus} sharesOf={sharesOf}
        sheetOpen={sheetOpen} setSheetOpen={setSheetOpen}
        onAbout={() => setAbout({ limits: false })} onCompare={openCompare}
      />
      <MapView
        catalog={catalog} active={active} selectedId={selectedId} onSelect={clickOnMap}
        hot={hot} onHot={setHot} fit={fit} focus={focus} sharesOf={sharesOf} nodeRequest={nodeRequest}
        detailsOpen={!!selected || (!phone && compareOpen)}
      />
      {selected && (
        <ErrorBoundary resetKey={selected.id} onClose={close}>
          <CityPanel
            agglomeration={selected} index={index} cities={cities} layers={layers}
            onShowLayer={showLayer} onClose={close} nodes={nodes} onPickNode={showNode}
          />
        </ErrorBoundary>
      )}
      {!selected && !phone && compareOpen && (
        <ErrorBoundary resetKey="compare" onClose={() => setCompareOpen(false)}>
          <Dock>
            <DetailsPanel title="Porównanie miast" onClose={() => setCompareOpen(false)}>{compare}</DetailsPanel>
          </Dock>
        </ErrorBoundary>
      )}
      {phone && compareSheet && (
        <Modal title="Porównanie miast" onClose={() => setCompareSheet(false)}>{compare}</Modal>
      )}
      {about && (
        <About
          catalog={catalog} metrics={metrics} attributions={attributions}
          toLimits={about.limits} onClose={() => setAbout(null)}
        />
      )}
    </AppShell>
  )
}
