import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AppMessage, AppShell, ErrorBoundary, Modal } from '@bartor-net/ui-kit'
import { loadAttributions, loadCatalog, loadClassShares, loadMetrics } from './data'
import { resolveUrl } from './config'
import {
  activeIds, chooseOverlay, revealLayer, setOverlayOn, setValue, setVariant,
} from './layerControl'
import { readHash, hashOfView, resolveHash } from './urlState'
import { DEFAULT_SHARE_AREA, scopeData } from './classShares'
import { allCities, indexMetrics, transportCities } from './metricTable'
import { outsideMask } from './outsideMask'
import { useFocuses } from './useFocuses'
import { loadNodeFeatures, useCityNodes } from './useCityNodes'
import { usePhone } from './usePhone'
import { CitiesClassBars, CityClassChart } from './ClassChart'
import MapView from './MapView'
import Sidebar from './Sidebar'
import CityPanel from './CityPanel'
import CityView from './CityView'
import Compare from './Compare'
import About from './About'
import DockStage from './kitx/DockStage'
import { refitOnChange } from './kitx/dock'
import { ACCENT } from './config'

const URL0 = readHash()
const FADED_KINDS = ['choropleth', 'mask', 'points']   // what is veiled outside the selected city
const LEGEND_LEFT_PAD = 300                             // px kept free on the left of a fitted city while the legend is open

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
  // how the cities are ordered in the two comparison tables: {key: metric id, dir} or null (the default order)
  const [sort, setSort] = useState(start.sort)
  const [sortDensity, setSortDensity] = useState(start.sortDensity)
  const [dock, setDock] = useState(start.dock)         // desktop: 'folded' | 'half' | 'full'
  const [tab, setTab] = useState('metrics')            // the tab of the comparison in the dock
  const [compareSheet, setCompareSheet] = useState(false)   // phones: the comparison as a modal
  const [shareArea, setShareArea] = useState(DEFAULT_SHARE_AREA)   // class shares: whole area or core city
  const [legendOpen, setLegendOpen] = useState(() => !(typeof window !== 'undefined' && window.matchMedia('(max-width: 760px)').matches))
  const [about, setAbout] = useState(null)           // null, or {limits}: the "O danych" modal
  const [nodeRequest, setNodeRequest] = useState(null)   // {layer, props, coordinates, n}
  const [shareDoc, setShareDoc] = useState({})
  useEffect(() => { loadClassShares().then(setShareDoc) }, [])

  const index = useMemo(() => indexMetrics(metrics.metrics), [metrics])
  const known = useMemo(() => catalog.agglomerations.map((a) => a.id), [catalog])
  const names = useMemo(() => Object.fromEntries(catalog.agglomerations.map((a) => [a.id, a.name])), [catalog])
  const cities = useMemo(() => transportCities(index, known), [index, known])
  const everyCity = useMemo(() => allCities(index, known), [index, known])

  const selected = catalog.agglomerations.find((a) => a.id === selectedId) || null
  const valueLayer = layers.find((l) => l.id === view.value && l.status === 'ready') || null

  // the veil over everything outside the selected city's area, built from the boundary file the map already draws
  const boundary = layers.find((l) => l.kind === 'boundary' && l.status === 'ready' && l.type === 'geojson' && l.url)
  const [boundaryFeatures, setBoundaryFeatures] = useState(null)
  useEffect(() => {
    if (!boundary) return undefined
    let dead = false
    loadNodeFeatures(resolveUrl(boundary.url)).then((f) => { if (!dead) setBoundaryFeatures(f) }).catch(() => {})
    return () => { dead = true }
  }, [boundary?.url])   // eslint-disable-line react-hooks/exhaustive-deps
  const fades = layers.some((l) => active.has(l.id) && FADED_KINDS.includes(l.kind))
  const outside = useMemo(
    () => (selectedId && fades && boundaryFeatures ? outsideMask(boundaryFeatures, selectedId) : null),
    [selectedId, fades, boundaryFeatures],
  )

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
      setSelectedId(null)
      setDock((d) => (d === 'folded' ? 'half' : d))
    }
  }, [phone])

  // fit the selected city again when the dock changes size (the map box changed); in full the map is the small inset
  const lastDock = useRef(dock)
  useEffect(() => {
    const prev = lastDock.current
    lastDock.current = dock
    if (phone || !refitOnChange(prev, dock) || !selected?.bbox) return
    setFit((f) => ({ bbox: selected.bbox, animate: false, n: (f?.n || 0) + 1 }))
  }, [dock])   // eslint-disable-line react-hooks/exhaustive-deps

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
    const h = hashOfView(selectedId, view, layers, { sort, sortDensity, dock })
    if (h !== window.location.hash && !(h === '' && !window.location.hash)) {
      window.history.replaceState(null, '', h || window.location.pathname + window.location.search)
    }
  }, [selectedId, view, layers, sort, sortDensity, dock])

  // what the legend and the charts know about the residents of the scope (the selected city, else all cities)
  const legendShares = useMemo(() => ({
    scopeOf: (layerId) => scopeData(shareDoc, layerId, selectedId, shareArea),
    aggName: selected?.name || null, area: shareArea, onArea: setShareArea,
  }), [shareDoc, selectedId, selected, shareArea])

  const cityChart = (
    <CityClassChart
      layer={valueLayer} doc={shareDoc} aggId={selectedId} aggName={selected?.name} area={shareArea} onArea={setShareArea}
      focus={focus}
    />
  )
  const citiesChart = (
    <CitiesClassBars
      layer={valueLayer} doc={shareDoc} cities={everyCity} names={names} area={shareArea} onArea={setShareArea}
      focus={focus} onPickCity={pick}
    />
  )
  const compare = (layout) => (
    <Compare
      index={index} cities={cities} everyCity={everyCity} names={names}
      area={area} setArea={setArea} layers={layers} onShowLayer={showLayer}
      onPickCity={pick} hot={hot} setHot={setHot}
      sort={sort} setSort={setSort} sortDensity={sortDensity} setSortDensity={setSortDensity}
      layout={layout} tab={tab} setTab={setTab} chart={citiesChart}
      onOpenLimits={() => setAbout({ limits: true })}
    />
  )
  const cityProps = {
    agglomeration: selected, index, cities, layers, onShowLayer: showLayer, nodes, onPickNode: showNode, chart: cityChart,
  }

  const map = (
    <MapView
      catalog={catalog} active={active} selectedId={selectedId} onSelect={clickOnMap}
      hot={hot} onHot={setHot} fit={fit} focus={focus} nodeRequest={nodeRequest} outside={outside}
      fitPad={dock === 'full' && !phone
        ? { top: 12, left: 12, right: 12, bottom: 12 }
        : { top: 40, left: legendOpen && !phone ? LEGEND_LEFT_PAD : 40, right: 40, bottom: 40 }}
      legendOpen={legendOpen} onLegendOpen={setLegendOpen} legendShares={legendShares}
    />
  )

  return (
    <AppShell>
      <Sidebar
        catalog={catalog} metrics={metrics} selectedId={selectedId} onPick={pick}
        view={view} active={active} onValue={onValue} onOverlayOn={onOverlayOn}
        onOverlayLayer={onOverlayLayer} onVariant={onVariant}
        sheetOpen={sheetOpen} setSheetOpen={setSheetOpen}
        onAbout={() => setAbout({ limits: false })} onCompare={openCompare}
      />
      {phone
        ? (
          <>
            {map}
            {selected && (
              <ErrorBoundary resetKey={selected.id} onClose={close}>
                <CityPanel {...cityProps} onClose={close} />
              </ErrorBoundary>
            )}
            {compareSheet && (
              <Modal title="Porównanie miast" onClose={() => setCompareSheet(false)}>{compare('stack')}</Modal>
            )}
          </>
        )
        : (
          <DockStage
            map={map} state={dock} onState={setDock}
            label={selected ? `Miary: ${selected.name}` : 'Porównanie miast'}
            title={selected
              ? (
                <>
                  <button type="button" className="dock-back" onClick={close}>← Porównanie miast</button>
                  <h2>{selected.name}</h2>
                  {selected.phase != null && <span className="dock-pill" style={{ background: ACCENT }}>Etap {selected.phase}</span>}
                </>
              )
              : <h2>Porównanie miast</h2>}
          >
            <ErrorBoundary resetKey={selected ? selected.id : 'compare'} onClose={close}>
              {selected
                ? <CityView {...cityProps} layout="columns" />
                : compare('tabs')}
            </ErrorBoundary>
          </DockStage>
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
