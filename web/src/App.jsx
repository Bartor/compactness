import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AppMessage, AppShell, ErrorBoundary, Modal } from '@bartor-net/ui-kit'
import { createDetailLoader } from './features/nodes/detailData'
import { useNodeDetail } from './features/nodes/useNodeDetail'
import useIsochroneMode from './features/isochrones/useIsochroneMode'
import IsochroneCard from './features/isochrones/IsochroneCard'
import { loadSurveyContext } from './features/context/surveyModel'
import SpeedTable from './features/speed/SpeedTable'
import { loadSpeedLines, resolvedLayer } from './features/speed/loader'
import { idsFilter, linesFilter } from './features/speed/lineLayers'
import { normaliseFilters, setFilter as setSpeedFilter, togglePin as togglePinnedLine } from './features/speed/lineTable'
import { bandOf } from './features/speed/speedModel'
import { loadAttributions, loadCatalog, loadClassShares, loadForm, loadMetrics } from './data'
import { DATA_BASE_URL, resolveUrl } from './config'
import { loadCharts } from './features/charts'
import { ExportContext } from './export/ExportContext'
import { metaFromRows } from './export/shape'
import MetricPage from './MetricPage'
import { pageAreas, pickArea } from './metricPageData'
import { allCities, indexMetrics, metricName, transportCities } from './metricTable'
import { CityCharts, ComparisonCharts } from './ChartsPanel'
import { togglePin } from './chartLink'
import {
  activeIds, chooseOverlay, revealLayer, setGroupVariant, setLayerOn, setOverlayOn, setValue, setVariant, sharedVariant,
} from './layerControl'
import { readHash, hashOfView, resolveHash } from './urlState'
import { scopeData, shareAreaOf } from './classShares'
import { outsideMask } from './outsideMask'
import { cityAtPoint } from './geo'
import { useFocuses } from './useFocuses'
import { loadNodeFeatures, useCityNodes } from './useCityNodes'
import { usePhone } from './usePhone'
import { CitiesClassBars, CityClassChart } from './ClassChart'
import Header from './Header'
import MapView from './MapView'
import Sidebar from './Sidebar'
import CityPanel from './CityPanel'
import CityView, { CITY_TABS } from './CityView'
import Compare, { COMPARE_TABS } from './Compare'
import About from './About'
import DockStage from './kitx/DockStage'
import Tabs, { panelId } from './kitx/Tabs'
import { refitOnChange } from './kitx/dock'

const URL0 = readHash()
const FADED_KINDS = ['choropleth', 'mask', 'points']   // what is veiled outside the selected city
const LEGEND_LEFT_PAD = 300                             // px kept free on the left of a fitted city while the legend is open
const POLAND_BBOX = [14.0, 48.9, 24.3, 54.9]
const SHEET_PEEK = 120   // phones: the map is fitted clear of the bottom sheet's peek
const LOW_WINDOW = 700                                  // px: below this, in the wide dock state, the layer list shrinks to the active layer

/** True while the window is lower than `px`. */
function useLowWindow(px) {
  const get = () => typeof window !== 'undefined' && window.innerHeight < px
  const [low, setLow] = useState(get)
  useEffect(() => {
    const on = () => setLow(get())
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  })
  return low
}

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
  const lowWindow = useLowWindow(LOW_WINDOW)
  const [sheetOpen, setSheetOpen] = useState(false)   // phones: the layers sheet
  // {bbox, animate, n}: a request to move the map; a selection or a position in the address is shown without animation
  const [fit, setFit] = useState(() => {
    if (start.mapView) return null
    const a = catalog.agglomerations.find((x) => x.id === start.agg)
    return a?.bbox ? { bbox: a.bbox, animate: false, n: 0 } : null
  })
  const [mapView, setMapView] = useState(start.mapView)   // where the user moved the map by hand (goes into the address)

  // the one global area every number refers to (an old address with the area of a metric page sets it too)
  const [area, setArea] = useState(start.area !== 'core' ? start.area : start.metricArea && start.metric ? start.metricArea : 'core')
  // the city lit on the map and in the tables: one state for both
  const [hot, setHot] = useState(null)
  const [pinnedCities, setPinnedCities] = useState(start.pinned)   // cities pinned in the charts (ids), lit in all of them
  // how the cities are ordered in the comparison table: {key: metric id, dir} or null (the default order)
  const [sort, setSort] = useState(start.sort)
  const [dock, setDock] = useState(start.dock)         // desktop: 'folded' | 'half' | 'full'
  const [compareTab, setCompareTab] = useState(COMPARE_TABS.some((t) => t.key === start.tab) ? start.tab : 'miary')
  const [cityTab, setCityTab] = useState(CITY_TABS.some((t) => t.key === start.tab) ? start.tab : 'najwazniejsze')
  const [compareSheet, setCompareSheet] = useState(false)   // phones: the comparison as a modal
  const [citySheet, setCitySheet] = useState(true)         // phones: the city's sheet is open (false: collapsed to a bar; the city stays)
  const [legendOpen, setLegendOpen] = useState(() => !(typeof window !== 'undefined' && window.matchMedia('(max-width: 760px)').matches))
  const [about, setAbout] = useState(null)           // null, or {limits}: the "O danych" modal
  const [nodeRequest, setNodeRequest] = useState(null)   // {layer, props, coordinates, n}
  const [flash, setFlash] = useState(null)           // {id, n}: a value layer changed by a link elsewhere (its card flashes)
  const [shareDoc, setShareDoc] = useState({})
  useEffect(() => { loadClassShares().then(setShareDoc) }, [])
  const [charts, setCharts] = useState(null)             // distribution charts (charts.json); null: no chart section
  useEffect(() => { loadCharts({ base: DATA_BASE_URL }).then(setCharts) }, [])
  // "Dokąd dojadę stąd": the switch, the picked origin (nearest precomputed) and the time of day shown
  const [isoOn, setIsoOn] = useState(!!start.iso)
  const pendingIso = useRef(start.iso)
  const [survey, setSurvey] = useState(null)             // household travel surveys (survey_context.json); null: no block
  useEffect(() => { loadSurveyContext().then(setSurvey) }, [])
  const [form, setForm] = useState(null)               // residents by density class per city (form.json), for metric pages
  useEffect(() => { loadForm().then(setForm) }, [])
  // the page of one metric: {id} or null; opened from a table row, linked by m= in the address
  const [metricPage, setMetricPage] = useState(() => (start.metric ? { id: start.metric } : null))
  const dockBefore = useRef(null)    // the dock state to return to when the page closes
  const pushed = useRef(false)       // the page's address entry was pushed (so Back closes it)
  const wasPage = useRef(false)
  const ran = useRef(false)          // the address effect has run once (a page open at load is not "opening")

  const index = useMemo(() => indexMetrics(metrics.metrics), [metrics])
  const isoActive = isoOn && !!selectedId
  const iso = useIsochroneMode(selectedId, isoActive)
  useEffect(() => { if (!selectedId && isoOn) setIsoOn(false) }, [selectedId, isoOn])
  useEffect(() => {
    if (iso.status === 'ready' && pendingIso.current) {
      iso.pickById(pendingIso.current)
      if (start.isoScenario) iso.setScenario(start.isoScenario)
      pendingIso.current = null
    }
  }, [iso.status])   // eslint-disable-line react-hooks/exhaustive-deps
  const exportMeta = useMemo(() => metaFromRows(metrics.metrics), [metrics])   // provenance written into every export
  const known = useMemo(() => catalog.agglomerations.map((a) => a.id), [catalog])
  const names = useMemo(() => Object.fromEntries(catalog.agglomerations.map((a) => [a.id, a.name])), [catalog])
  const cities = useMemo(() => transportCities(index, known), [index, known])     // the seven with timetables
  const everyCity = useMemo(() => allCities(index, known), [index, known])         // all agglomerations, the seven first

  const selected = catalog.agglomerations.find((a) => a.id === selectedId) || null
  const valueLayer = layers.find((l) => l.id === view.value && l.status === 'ready') || null
  const hasPoints = layers.some((l) => l.kind === 'points' && l.status === 'ready')

  // the boundary file the map draws: the veil outside the selected city and the "which city is here" lookup come from it
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
  const cityAt = useCallback((lng, lat) => cityAtPoint(boundaryFeatures, lng, lat), [boundaryFeatures])

  // ---- moving between the views
  const fitTo = useCallback((bbox, animate = true) => {
    setMapView(null)
    setFit((f) => ({ bbox, animate, n: (f?.n || 0) + 1 }))
  }, [])
  // picked in the list or on the map: fly there
  const pick = useCallback((id) => {
    setSelectedId(id)
    setHot(null)
    if (id) {
      setCitySheet(true)
      setSheetOpen(false)   // two stacked sheets would leave no map to look at
      setCompareSheet(false)
      const a = catalog.agglomerations.find((x) => x.id === id)
      if (a?.bbox) fitTo(a.bbox)
    }
  }, [catalog, fitTo])
  const clickOnMap = useCallback((id, far) => {
    if (far) return pick(id)   // clicked from far out: go there
    setSelectedId(id)
    setSheetOpen(false)
  }, [pick])
  // the panel's "← Porównanie" and the name in the header: no city, the whole country in view, the layer kept
  const closeNow = useCallback(() => {
    setMetricPage(null)
    if (dockBefore.current != null) { setDock(dockBefore.current); dockBefore.current = null }
    pushed.current = false
  }, [])
  const toComparison = useCallback(() => {
    setSelectedId(null)
    setHot(null)
    setCompareSheet(false)
    fitTo(POLAND_BBOX)
  }, [fitTo])
  const home = useCallback(() => {
    closeNow()
    toComparison()
    setCompareTab('miary')
    setSheetOpen(false)
  }, [closeNow, toComparison])
  const openCompare = useCallback(() => {
    if (phone) { setSheetOpen(false); setCompareSheet(true) } else toComparison()
  }, [phone, toComparison])

  // fit the selected city again when the dock changes size (the map box changed); in full the map is the small one
  // A move that arrives together with the dock change (a city picked from the full metric page closes the page and flies
  // there) was already fitted to the final box by the map: a second, instant fit would cut that flight short.
  const lastDock = useRef(dock)
  const lastFit = useRef(fit)
  useEffect(() => {
    const prev = lastDock.current
    const fitMoved = lastFit.current !== fit
    lastDock.current = dock
    lastFit.current = fit
    if (phone || fitMoved || !refitOnChange(prev, dock) || !selected?.bbox) return
    setFit((f) => ({ bbox: selected.bbox, animate: false, n: (f?.n || 0) + 1 }))
  }, [dock, fit])   // eslint-disable-line react-hooks/exhaustive-deps
  const settled = useCallback(() => { if (selected?.bbox) setFit((f) => ({ bbox: selected.bbox, animate: false, n: (f?.n || 0) + 1 })) }, [selected])

  // layer controls
  // on a phone choosing a layer folds the layers sheet to its peek, so the result is seen at once
  const onValue = useCallback((id) => { setView((v) => setValue(v, id, layers)); if (phone) setSheetOpen(false) }, [layers, phone])
  const onOverlayOn = useCallback((kind, on) => setView((v) => setOverlayOn(v, kind, on)), [])
  const onOverlayLayer = useCallback((kind, id) => setView((v) => chooseOverlay(v, kind, id, layers)), [layers])
  const onLayerOn = useCallback((kind, id, on) => setView((v) => setLayerOn(v, kind, id, on, layers)), [layers])
  // the scheduled-speed overlay: one band for all its layers; a new day type keeps the same time of day where it can
  const speedBand = sharedVariant(view, 'lines', layers)
  const onBand = useCallback((day, key) => setView((v) => {
    const cur = sharedVariant(v, 'lines', layers)
    const next = key || setSpeedFilter({ day: bandOf(cur).day, band: cur }, 'day', day).band
    return setGroupVariant(v, 'lines', next, layers)
  }), [layers])
  const onVariant = useCallback((layer, key) => setView((v) => setVariant(v, layer, key)), [])
  // "pokaż na mapie" in a table: show that layer, whichever kind it is; a value layer's card flashes in the sidebar
  const reveal = useCallback((id) => {
    setView((v) => revealLayer(v, layers, id))
    if (layers.find((l) => l.id === id)?.kind === 'choropleth') setFlash((f) => ({ id, n: (f?.n || 0) + 1 }))
  }, [layers])
  const showLayer = useCallback((id) => {
    reveal(id)
    if (phone) setCompareSheet(false)
  }, [reveal, phone])

  // the busiest stop areas of the selected city: from the points layer chosen for the nodes overlay
  const pointsGroup = view.overlays.points
  const pointsLayer = pointsGroup ? layers.find((l) => l.id === pointsGroup.layer && l.status === 'ready') : null
  const [nodeOrder, setNodeOrder] = useState('dep')   // the list of stop areas: by departures or by share of transfers
  const nodes = useCityNodes(pointsLayer, selectedId, 8, nodeOrder)
  // the card of one stop area (a record in transfer_detail/<agg>.json): desktop only; elsewhere the popup stays
  const detailLoader = useMemo(() => createDetailLoader(), [])
  const [nodePick, setNodePick] = useState(null)         // {id, name, agg} or null
  const [nodeHot, setNodeHot] = useState({ move: null, path: null })
  const pickedNode = nodePick && nodePick.agg === selectedId ? nodePick : null   // changing city closes the card
  const detail = useNodeDetail(detailLoader, pickedNode?.id)
  useEffect(() => { if (selectedId) detailLoader.prefetch(selectedId) }, [selectedId, detailLoader])
  const closeNode = useCallback(() => { setNodePick(null); setNodeHot({ move: null, path: null }) }, [])
  const openNode = useCallback((props) => {
    setNodePick({ id: props.id, name: props.name, agg: props.agg })
    setNodeHot({ move: null, path: null })
    setCityTab('przesiadki')
    setDock((d) => (d === 'folded' ? 'half' : d))
    setMetricPage(null)
    if (props.agg && props.agg !== selectedId) pick(props.agg)
  }, [selectedId, pick])
  const showNode = useCallback((layer, n) => {
    setView((v) => revealLayer(v, layers, layer.id))
    if (n.props?.detail && !phone) { openNode(n.props); return }
    setNodeRequest((r) => ({ layer, props: n.props, coordinates: n.coordinates, n: (r?.n || 0) + 1 }))
  }, [layers, phone, openNode])
  useEffect(() => { if (nodePick && !view.overlays.points?.on) closeNode() }, [view, nodePick, closeNode])

  // ---- scheduled speeds: the layers drawn by the map (the bus file depends on the city, every layer carries the shared band),
  // the lines table of the "Prędkości" tab, and the lit / pinned lines it shares with the map
  const mapCatalog = useMemo(() => ({
    ...catalog,
    layers: catalog.layers.map((l) => {
      if (l.kind !== 'lines') return l
      const r = l.url_template ? (resolvedLayer(l, selectedId) || { ...l, url: null }) : l
      return { ...r, band: speedBand }
    }),
  }), [catalog, selectedId, speedBand])
  const hasSpeed = layers.some((l) => l.kind === 'lines' && l.status === 'ready')
  const [speedMode, setSpeedMode] = useState('tram')
  const [speedData, setSpeedData] = useState({ status: 'idle', data: null })
  const [lineTableHot, setLineTableHot] = useState(null)   // row keys lit from the table
  const [lineMapHover, setLineMapHover] = useState(null)   // {id, keys} of the stretch under the pointer
  const [linePinned, setLinePinned] = useState([])         // row keys pinned in the table
  const onLineHover = useCallback((h) => setLineMapHover((cur) => (cur?.id === h?.id ? cur : h)), [])
  useEffect(() => { setLinePinned([]); setLineTableHot(null) }, [selectedId])
  const lineHotFilter = lineMapHover ? idsFilter([lineMapHover.id]) : lineTableHot?.length ? linesFilter(lineTableHot) : null
  const linePinFilter = useMemo(() => (linePinned.length ? linesFilter(linePinned) : null), [linePinned])
  const loadSpeed = useCallback(() => {
    setSpeedData((d) => (d.status === 'idle' || d.status === 'error' ? { status: 'loading', data: null } : d))
    loadSpeedLines(resolveUrl).then((data) => setSpeedData({ status: 'ready', data }), () => setSpeedData({ status: 'error', data: null }))
  }, [])
  const speedFilters = normaliseFilters({ city: selectedId, mode: speedMode, day: bandOf(speedBand).day, band: speedBand })
  // a mode chosen in the table is shown on the map too
  const showSpeedMode = useCallback((mode) => {
    for (const l of layers) {
      if (l.kind === 'lines' && l.status === 'ready' && l.mode_group === mode && (!l.needs_city || selectedId)) setView((v) => revealLayer(v, layers, l.id))
    }
  }, [layers, selectedId])
  const onSpeedFilters = useCallback((f) => {
    if (f.mode !== speedMode) { setSpeedMode(f.mode); if (f.mode !== 'all') showSpeedMode(f.mode) }
    if (f.band !== speedBand) setView((v) => setGroupVariant(v, 'lines', f.band, layers))
  }, [speedMode, speedBand, layers, showSpeedMode])

  // ---- the page of one metric
  const page = metricPage && index[metricPage.id] && pageAreas(index, metricPage.id).length ? { id: metricPage.id } : null
  const openMetric = useCallback((id) => {
    setMetricPage({ id })
    if (!phone) {
      if (!wasPage.current && dockBefore.current == null) dockBefore.current = dock
      setDock('full')
    }
  }, [phone, dock])
  // the "wróć" button, Escape: step back in the history when the page pushed an entry, so that Back and "wróć" agree
  const closePage = useCallback(() => {
    if (pushed.current) window.history.back()
    else closeNow()
  }, [closeNow])
  useEffect(() => {
    const onPop = () => {
      const r = readHash()
      if (r.metric) setMetricPage({ id: r.metric })
      else closeNow()
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [closeNow])
  const showOnMap = useCallback((layerId) => {
    reveal(layerId)
    dockBefore.current = 'half'
    closeNow()
  }, [reveal, closeNow])
  const pickFromPage = (c) => { closeNow(); pick(c) }

  // Escape closes the nearest thing: a stop popup (MapView), an open "?" (here), the metric page (its own listener)
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Escape') return
      const open = document.querySelector('.kit-help-btn[aria-expanded="true"]')
      if (open) { e.stopPropagation(); open.click() }
    }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [])

  // Keep the address in step: no history entry per click, except one when a metric page opens
  const comparisonView = !selected && !page
  const tab = page ? undefined : selected ? (cityTab !== 'najwazniejsze' ? cityTab : undefined) : (compareTab !== 'miary' ? compareTab : undefined)
  useEffect(() => {
    const h = hashOfView(selectedId, view, layers, {
      sort: comparisonView ? sort : undefined, dock, metric: page?.id, area, tab, pinned: pinnedCities, mapView,
      iso: isoActive ? iso.origin?.id : undefined, isoScenario: iso.scenario,
    })
    const opening = !!page && !wasPage.current
    wasPage.current = !!page
    if (h !== window.location.hash && !(h === '' && !window.location.hash)) {
      const url = h || window.location.pathname + window.location.search
      if (opening && ran.current) { window.history.pushState(null, '', url); pushed.current = true } else window.history.replaceState(null, '', url)
    }
    ran.current = true
  }, [selectedId, view, layers, sort, comparisonView, dock, page?.id, area, tab, pinnedCities, mapView, isoActive, iso.origin?.id, iso.scenario])   // eslint-disable-line react-hooks/exhaustive-deps

  // ---- what the legend and the charts know about the residents of the scope (the selected city, else all cities)
  const legendShares = useMemo(() => ({
    scopeOf: (layerId) => scopeData(shareDoc, layerId, selectedId, shareAreaOf(area)),
    aggName: selected?.name || null, area,
    noDataFor: (layerId) => !!(selectedId && shareDoc?.layers?.[layerId] && !shareDoc.layers[layerId][selectedId]),
  }), [shareDoc, selectedId, selected, area])

  const link = { hot, setHot, pinned: pinnedCities, onPin: (id) => id && setPinnedCities((p) => togglePin(p, id)) }
  const cityChart = <CityClassChart layer={valueLayer} doc={shareDoc} aggId={selectedId} aggName={selected?.name} area={area} focus={focus} />
  const citiesChart = (
    <CitiesClassBars
      layer={valueLayer} doc={shareDoc} cities={everyCity} names={names} area={area}
      focus={focus} onPickCity={pick} hot={hot} onHot={setHot} pinned={pinnedCities}
    />
  )
  const spreadCities = charts ? <ComparisonCharts charts={charts} layer={valueLayer} focus={focus} link={link} area={area} /> : null
  const cityCharts = (parts) => (charts && selected
    ? <CityCharts charts={charts} layer={valueLayer} focus={focus} link={link} agg={selected.id} area={area} parts={parts} />
    : null)
  const compare = (layout) => (
    <Compare
      index={index} cities={cities} everyCity={everyCity} names={names}
      area={area} layers={layers} onShowLayer={showLayer}
      onPickCity={pick} hot={hot} setHot={setHot} onOpenMetric={openMetric}
      sort={sort} setSort={setSort}
      layout={layout} tab={compareTab} chart={citiesChart} spread={spreadCities}
      onOpenLimits={() => setAbout({ limits: true })}
    />
  )
  const hasTimetable = selected ? cities.includes(selected.id) : false
  const cityTabs = CITY_TABS.filter((t) => (t.key !== 'przesiadki' || hasPoints) && (t.key !== 'predkosci' || (hasSpeed && !phone && hasTimetable)) && (t.key !== 'wykresy' || (charts && hasTimetable)))
  const activeCityTab = cityTabs.some((t) => t.key === cityTab) ? cityTab : 'najwazniejsze'
  // the lines table is loaded when its tab first opens, and the lines of its mode appear on the map
  useEffect(() => {
    if (activeCityTab !== 'predkosci') return
    if (speedData.status === 'idle') loadSpeed()
    if (!layers.some((l) => l.kind === 'lines' && active.has(l.id))) showSpeedMode(speedMode === 'all' ? 'tram' : speedMode)
  }, [activeCityTab])   // eslint-disable-line react-hooks/exhaustive-deps
  const speedTable = speedData.status === 'ready'
    ? (
      <SpeedTable
        data={speedData.data} filters={speedFilters} onFilters={onSpeedFilters}
        hot={lineMapHover?.keys || lineTableHot} onHot={setLineTableHot}
        pinned={linePinned} onPin={(k) => setLinePinned((p) => togglePinnedLine(p, k))}
      />
    )
    : null
  const cityProps = selected && {
    agglomeration: selected, index, pool: everyCity, transport: cities, layers, area, onShowLayer: showLayer, nodes, onPickNode: showNode,
    chart: cityChart, timeChart: hasTimetable ? cityCharts(['timeofday']) : null,
    spread: hasTimetable ? cityCharts(['atleast', 'reach', 'dotstrip']) : null,
    onOpenMetric: openMetric, hasPoints, tab: activeCityTab, survey, speed: speedTable, speedStatus: speedData.status, onSpeedRetry: loadSpeed,
    nodePick: pickedNode, detail, nodeHot, onNodeHot: (move, path) => setNodeHot({ move, path }), onNodeClose: closeNode,
    nodeOrder, onNodeOrder: setNodeOrder, timetableDate: pointsLayer?.timetable_date,
  }
  const citySubtitle = selected ? (hasTimetable ? 'z danymi o transporcie' : 'tylko gęstość i forma (bez rozkładów jazdy)') : ''
  const densityColors = layers.find((l) => l.id === 'density_250m')?.ramp?.colors
  const pageArea = page ? pickArea(index, page.id, area) : null
  const metricPageEl = page && (
    <MetricPage
      id={page.id} area={pageArea} asked={area} from={selectedId}
      index={index} cities={cities} everyCity={everyCity} names={names} charts={charts} form={form} densityColors={densityColors}
      layers={layers} link={link} onClose={closePage} onPickCity={pickFromPage} onShowLayer={showOnMap}
      onNavigate={(mid) => setMetricPage({ id: mid })}
    />
  )

  const map = (
    <MapView
      catalog={mapCatalog} active={active} selectedId={selectedId} onSelect={clickOnMap}
      lineHot={lineHotFilter} linePin={linePinFilter} onLineHover={onLineHover}
      hot={hot} onHot={setHot} fit={fit} focus={focus} nodeRequest={nodeRequest} outside={outside}
      onNode={phone ? undefined : openNode} detailNode={pickedNode && detail.status === 'ready' ? detail.node : null} hotPath={nodeHot.path}
      fitPad={dock === 'full' && !phone
        ? { top: 12, left: 12, right: 12, bottom: 12 }
        : { top: 40, left: legendOpen && !phone ? LEGEND_LEFT_PAD : 40, right: 40, bottom: phone ? (selected && citySheet ? Math.round(window.innerHeight * 0.7) : SHEET_PEEK) : 40 }}
      legendOpen={legendOpen} onLegendOpen={setLegendOpen} legendShares={legendShares}
      isoOn={isoActive} isoLayers={isoActive ? iso.layers : null}
      onIsoPick={(p) => { iso.pick(p); setLegendOpen(true) }}
      legendExtra={isoActive
        ? <IsochroneCard file={iso.file} status={iso.status} origin={iso.origin} distanceM={iso.distanceM} scenario={iso.scenario} onScenario={iso.setScenario} onClose={() => setIsoOn(false)} />
        : null}
      cityAt={cityAt} onMoved={setMapView} initialView={start.mapView}
    />
  )
  const full = dock === 'full' && !phone
  const sidebar = (
    <Sidebar
      catalog={catalog} view={view} onValue={onValue} onOverlayOn={onOverlayOn}
      onOverlayLayer={onOverlayLayer} onVariant={onVariant} flash={flash}
      agg={selectedId} onLayerOn={onLayerOn} onBand={onBand}
      sheetOpen={sheetOpen} setSheetOpen={setSheetOpen} onAbout={() => setAbout({ limits: false })}
      selectedName={selected?.name} collapsed={full && lowWindow}
      iso={{ on: isoOn, enabled: !!selectedId, onChange: setIsoOn }}
    />
  )

  const dockTitle = page
    ? <h2>Miara: {metricName(index, page.id)}</h2>
    : selected
      ? (
        <>
          <button type="button" className="dock-back" onClick={toComparison}>← Porównanie</button>
          <h2>{selected.name}</h2>
          <span className="dock-sub">{citySubtitle}</span>
        </>
      )
      : <h2>Porównanie aglomeracji</h2>
  const dockTabs = page
    ? null
    : selected
      ? <Tabs tabs={cityTabs} value={activeCityTab} onChange={setCityTab} label="Widoki aglomeracji" prefix="dock" />
      : <Tabs tabs={COMPARE_TABS} value={compareTab} onChange={setCompareTab} label="Widoki porównania" prefix="dock" />

  return (
    <ExportContext.Provider value={exportMeta}>
      <div className={`app-root${full ? ' full' : ''}`}>
        <Header
          catalog={catalog} selectedId={selectedId} onPick={(id) => { closeNow(); if (id) pick(id); else toComparison() }} onHome={home}
          area={area} onArea={setArea} onAbout={() => setAbout({ limits: false })} onCompare={openCompare} phone={phone}
        />
        <AppShell>
          {sidebar}
          {phone
            ? (
              <>
                {map}
                {selected && !citySheet && (
                  <button type="button" className="city-peek" onClick={() => setCitySheet(true)} aria-label={`Pokaż panel: ${selected.name}`}>
                    <b>{selected.name}</b><span>pokaż liczby ▴</span>
                  </button>
                )}
                {selected && citySheet && (
                  <ErrorBoundary resetKey={selected.id} onClose={toComparison}>
                    <CityPanel
                      {...cityProps} subtitle={citySubtitle} tabs={cityTabs} setTab={setCityTab} onClose={() => setCitySheet(false)} onBack={() => { toComparison(); setCompareSheet(true) }}
                      layout="stack"
                    />
                  </ErrorBoundary>
                )}
                {compareSheet && (
                  <Modal title="Porównanie aglomeracji" onClose={() => setCompareSheet(false)}>{compare('stack')}</Modal>
                )}
                {page && <Modal title={metricName(index, page.id)} onClose={closePage}>{metricPageEl}</Modal>}
              </>
            )
            : (
              <DockStage
                map={map} state={dock} onState={setDock} onSettle={settled}
                label={page ? `Miara: ${metricName(index, page.id)}` : selected ? `Aglomeracja: ${selected.name}` : 'Porównanie aglomeracji'}
                title={dockTitle} tabs={dockTabs}
              >
                <ErrorBoundary resetKey={`${selected ? selected.id : 'compare'}${page ? page.id : ''}`} onClose={toComparison}>
                  <div role={page ? undefined : 'tabpanel'} id={page ? undefined : panelId('dock')} className="dock-panel">
                    {page
                      ? metricPageEl
                      : selected
                        ? <CityView {...cityProps} layout="columns" />
                        : compare('tabs')}
                  </div>
                </ErrorBoundary>
              </DockStage>
            )}
        </AppShell>
        {about && (
          <About
            catalog={catalog} metrics={metrics} attributions={attributions}
            toLimits={about.limits} onClose={() => setAbout(null)}
          />
        )}
      </div>
    </ExportContext.Provider>
  )
}
