import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import { buildStyle, hatchImage } from './mapStyle'
import { applyHot, fillId, syncOverlays } from './mapLayers'
import { classIndex, focusOpacity, rampLegend } from './ramp'
import { syncIsochrones } from './features/isochrones/isoLayers'
import { clearNodeDetail, detailBounds, setHotPath, showNodeDetail } from './features/nodes/detailLayers'
import { ANCHOR_LABELS } from './mapStyle'
import { emphasised, focusOf, hoverOnMap, leaveMap } from './classFocus'
import { applyFocus, pointLayerIds } from './pointLayers'
import { nodePopupModel, panToFit, placePopup, renderNodePopup } from './nodePopup'
import { applyLines, hitBox, hitTest, lineLayerIds } from './features/speed/lineLayers'
import { renderStretchPopup, stretchPopupModel } from './features/speed/stretchPopup'
import { tipModel } from './features/segments/segText'
import { ensureVisible, renderLineTip } from './features/segments/segMap'
import Legend from './Legend'
// MapLibre 6 looks for its worker next to its own module; once bundled, that
// file is not there. Emitting it as an asset and naming it keeps dev and the
// production build on the same path.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

maplibregl.setWorkerUrl(workerUrl)

// PMTiles are read straight from static hosting with range requests.
let protocolReady = false
function registerPmtiles() {
  if (protocolReady) return
  maplibregl.addProtocol('pmtiles', new Protocol().tile)
  protocolReady = true
}

const HIT_PAD = 4
// every agglomeration of the comparison in view: the first sight and "home" are the same fit (App's POLAND_BBOX)
const POLAND_BOUNDS = [[14.0, 48.9], [24.3, 54.9]]
const isPhone = () => window.matchMedia('(max-width: 760px)').matches

// Desktop padding for fitBounds: the page passes it (`fitPad`), clear of the legend in the corner. The dock is not
// in it: it sits under the map and the map box already ends above it.
const DEFAULT_PAD = { top: 40, left: 40, right: 40, bottom: 40 }
const PHONE_PAD = { top: 24, left: 20, right: 20, bottom: 120 }

/**
 * The padding of a fit, as the map stands now. The left side clears the legend only when the legend is tall enough to
 * get in the way (the classes of a data layer): a short one (the boundaries alone) sits in the corner under the
 * outline, and leaving a third of the map empty for it puts the city visibly off-centre.
 */
function padNow(cont, fitPad) {
  const cb = cont.getBoundingClientRect()
  // a phone: the sheet covers the bottom of the map (the page says how much), but some map always stays
  if (isPhone()) return { ...PHONE_PAD, bottom: Math.max(PHONE_PAD.bottom, Math.min((fitPad.bottom || 0) + 40, cb.height - 150)) }
  const r = cont.parentElement?.querySelector('.kit-map-legend')?.getBoundingClientRect()
  const tall = !!r && r.height > 0 && r.height >= cb.height * 0.4
  return { ...fitPad, left: tall ? Math.round(r.right - cb.left) + 16 : Math.min(fitPad.left, 40) }
}

// The kit's .kit-map-wrap supplies the sizing: a flex child that fills what
// the sidebar leaves, and the whole screen behind the sheets on phones.
export default function MapView({
  catalog, active, selectedId, hot, onHot, onSelect, fit, fitPad = DEFAULT_PAD, focus, nodeRequest, outside = null,
  legendOpen, onLegendOpen, legendShares, cityAt, onMoved, initialView = null,
  isoOn = false, isoLayers = null, onIsoPick, legendExtra = null, onNode, detailNode = null, hotPath = null,
  lineHot = null, linePin = null, onLineHover,
  lineSel = null, onLinePick, inset = false, onInset, side = null, selBounds = null, selN = 0,
}) {
  const { focuses, setFocuses } = focus
  const box = useRef(null)
  const map = useRef(null)
  const latest = useRef({})
  // the map object once its style has loaded; the object itself, so that a map
  // removed by a StrictMode remount can never be mistaken for the live one
  const [ready, setReady] = useState(null)
  const [mapError, setMapError] = useState(null)
  // colour classes hovered or pinned per layer live in App (useFocuses): the sidebar legend shares them
  // the open stop-area popup and the layer it belongs to
  const popup = useRef(null)
  const showPopup = useRef(null)   // opens the popup of a node: {layer, feature}

  // what the long-lived map handlers need to see
  latest.current = { catalog, onSelect, active, onHot, cityAt, onMoved, isoOn, selectedId, onIsoPick, onNode, onLineHover, onLinePick, inset, onInset }
  const [loading, setLoading] = useState(false)   // tiles of a layer are still coming
  const tip = useRef(null)
  const ltip = useRef(null)

  useEffect(() => {
    registerPmtiles()
    let m
    try {
      m = new maplibregl.Map({
        container: box.current,
        style: buildStyle(),
        ...(initialView
          ? { center: [initialView.lon, initialView.lat], zoom: initialView.zoom }
          : { bounds: POLAND_BOUNDS, fitBoundsOptions: { padding: padNow(box.current, fitPad) } }),
        minZoom: 3,
        maxZoom: 17,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
        fadeDuration: 0,
      })
    } catch (e) {
      setMapError(e.message || String(e))
      return undefined
    }
    map.current = m
    if (import.meta.env.DEV) window.__map = m   // for looking at the map from the console while developing
    let dead = false
    m.touchZoomRotate.disableRotation()
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    m.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left')
    // Layer attributions come with their sources, and OpenFreeMap's own with the
    // basemap's TileJSON; this one is always there.
    const attrib = new maplibregl.AttributionControl({
      compact: isPhone() || undefined,
      customAttribution: [
        '© współtwórcy <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
      ],
    })
    m.addControl(attrib, 'bottom-right')
    // on a phone the attribution stays folded to its "i" until it is asked for (layers add their sources and open it)
    let folded = 0
    const foldAttribution = () => {
      if (!isPhone() || folded > 4) return
      folded += 1
      const c = attrib._container
      if (c) { c.removeAttribute('open'); c.classList.remove('maplibregl-compact-show') }
    }
    for (const ev of ['load', 'sourcedata', 'idle']) m.on(ev, foldAttribution)

    m.on('load', () => {
      if (dead) return
      m.addImage('hatch', hatchImage(), { pixelRatio: 2 })
      setReady(m)
    })
    // a quiet "loading" state while tiles are on their way
    const busy = () => { if (!dead) setLoading(!m.areTilesLoaded()) }
    for (const ev of ['sourcedataloading', 'sourcedata', 'idle']) m.on(ev, busy)
    // the position after a move by hand goes into the address (programmatic moves have no original event)
    m.on('moveend', (e) => {
      if (!e.originalEvent) return
      const c = m.getCenter()
      latest.current.onMoved?.({ lat: c.lat, lon: c.lng, zoom: m.getZoom() })
    })
    // a failed tile or file must not take the page down
    m.on('error', (e) => console.warn('map:', e.error?.message || e))

    const boundaryHits = (point) => {
      const ids = latest.current.catalog.layers
        .filter((l) => l.kind === 'boundary')
        .map(fillId)
        .filter((id) => m.getLayer(id))
      return ids.length ? m.queryRenderedFeatures(point, { layers: ids }) : []
    }
    const known = (id) => latest.current.catalog.agglomerations.some((a) => a.id === id)
    // shown points layers; a node under a point: {layer, feature} or null
    const pointsLayers = () => {
      const { catalog: c, active: on } = latest.current
      return c.layers.filter((l) => l.kind === 'points' && on.has(l.id))
    }
    const nodeHit = (point) => {
      for (const l of pointsLayers()) {
        const ids = pointLayerIds(l).filter((id) => m.getLayer(id))
        if (!ids.length) continue
        // a few pixels of slack: the small nodes are hard to hit with a finger
        const box = [[point.x - HIT_PAD, point.y - HIT_PAD], [point.x + HIT_PAD, point.y + HIT_PAD]]
        const f = m.queryRenderedFeatures(box, { layers: ids })[0]
        if (f) return { layer: l, feature: f }
      }
      return null
    }
    const closePopup = () => {
      if (popup.current) popup.current.remove()
      popup.current = null
    }
    // A popup is placed so that it lies wholly in the visible map: below the point, above it, or beside it, whichever has room
    // (nodePopup.js placePopup), clear of the legend and the zoom buttons where that is possible and always clear of the
    // attribution strip. Its content scrolls inside when it is taller than the room; when no anchor fits, the map pans once
    // by the least that makes it fit.
    const openContent = (content, lngLat, layerId) => {
      closePopup()
      const cont = m.getContainer()
      const M = 12
      const OFF = 8
      const cb = cont.getBoundingClientRect()
      const rel = (r) => ({ left: r.left - cb.left, top: r.top - cb.top, right: r.right - cb.left, bottom: r.bottom - cb.top })
      const shown = (sel, root) => [...root.querySelectorAll(sel)].map((e) => e.getBoundingClientRect()).filter((r) => r.width > 0 && r.height > 0).map(rel)
      // the strip along the bottom (attribution, scale) is not available to the popup
      const strip = Math.min(cb.height - M, ...shown('.maplibregl-ctrl-attrib, .maplibregl-ctrl-scale', cont).map((r) => r.top - 4))
      const area = { left: M, top: M, right: cb.width - M, bottom: strip }
      const avoid = [...shown('.maplibregl-ctrl-top-left .maplibregl-ctrl-group', cont), ...shown('.kit-map-legend', cont.parentElement)]
      const build = (anchor) => new maplibregl.Popup({ maxWidth: 'none', className: 'node-popup-wrap', focusAfterOpen: false, offset: OFF, anchor })
        .setLngLat(lngLat).setDOMContent(content).addTo(m)
      content.style.maxHeight = '420px'
      let p = build('top')
      let r0 = p.getElement().getBoundingClientRect()
      // the popup, tip and padding included, must fit the room that is left: shorten the scrolling content by the excess
      const room = area.bottom - area.top - OFF
      if (r0.height > room) {
        content.style.maxHeight = `${Math.max(80, content.offsetHeight - (r0.height - room))}px`
        r0 = p.getElement().getBoundingClientRect()
      }
      const place = placePopup({ point: m.project(lngLat), size: { w: r0.width, h: r0.height }, area, avoid, offset: OFF })
      p.remove()
      p = build(place.anchor)
      p.layerId = layerId
      p.on('close', () => { if (popup.current === p) popup.current = null })
      popup.current = p
      // what the measured popup still lacks (a tip that is a pixel or two off, a stretch of room that is not there): pan once
      const [dx, dy] = panToFit(rel(p.getElement().getBoundingClientRect()), area)
      if (Math.abs(dx) >= 1 || Math.abs(dy) >= 1) m.panBy([Math.round(dx), Math.round(dy)], { duration: 250 })
    }
    const openPopup = ({ layer, feature }) => {
      openContent(renderNodePopup(nodePopupModel(feature.properties || {}, layer.timetable_date)), feature.geometry.coordinates.slice(), layer.id)
    }
    // the scheduled-speed stretches under a point: {layer, hit} of the topmost active "lines" layer, or null
    const lineLayersOn = () => {
      const { catalog: c, active: on } = latest.current
      return c.layers.filter((l) => l.kind === 'lines' && on.has(l.id))
    }
    const lineHit = (point) => {
      for (const l of lineLayersOn()) {
        const ids = lineLayerIds(l).filter((id) => m.getLayer(id))
        if (!ids.length) continue
        const hit = hitTest(l, m.queryRenderedFeatures(hitBox(point), { layers: ids }), l.band)
        if (hit) return { layer: l, hit }
      }
      return null
    }
    const openStretch = ({ layer, hit }, lngLat) => {
      openContent(renderStretchPopup(stretchPopupModel(hit.properties, layer.band, layer.timetable_dates || null)), [lngLat.lng, lngLat.lat], layer.id)
    }
    showPopup.current = openPopup
    // Escape closes the popup first (the nearest thing); the page's other Escape handlers then do not run
    const onEscape = (e) => { if (e.key === 'Escape' && popup.current) { e.stopPropagation(); closePopup() } }
    document.addEventListener('keydown', onEscape, true)
    m.on('click', (e) => {
      // the small map beside a full panel: no popup and no selection there (they would not fit), the click brings the large map back
      if (latest.current.inset) { closePopup(); latest.current.onInset?.(); return }
      // a click on a node opens its popup and leaves the selected agglomeration alone
      const node = nodeHit(e.point)
      if (node) {
        // a stop area with a detail record opens its card in the panel (desktop); the others keep the popup
        const props = node.feature.properties || {}
        if (props.detail && !isPhone() && latest.current.onNode) {
          closePopup()
          latest.current.onNode(props)
          return
        }
        openPopup(node)
        return
      }
      // a stretch of a line (unless the isochrone mode wants the click for its origin)
      if (!latest.current.isoOn) {
        const ln = lineHit(e.point)
        // a speed feature is selected (the panel on the right shows the selection); without a handler, the old popup
        if (ln && latest.current.onLinePick) { closePopup(); latest.current.onLinePick({ layer: ln.layer, id: ln.hit.id, properties: ln.hit.properties }); return }
        if (ln) { openStretch(ln, e.lngLat); return }
      }
      const hits = boundaryHits(e.point).filter((f) => known(f.properties?.id)).map((f) => f.properties.id)
      const id = hits[0] ?? latest.current.cityAt?.(e.lngLat.lng, e.lngLat.lat)
      // "Dokąd dojadę stąd": a click inside the selected city picks the nearest precomputed origin; another city is still selected
      const { isoOn: on, selectedId: sel, onIsoPick: pickIso } = latest.current
      if (on && sel && pickIso && (id === sel || hits.includes(sel))) { pickIso([e.lngLat.lng, e.lngLat.lat]); return }
      // from the whole-country view an area is a speck: tell the app, so it can zoom in
      if (id && known(id)) latest.current.onSelect(id, m.getZoom() < 7.5)
    })
    // the value-layer class under the pointer, per layer with classes: {layerId: index}
    const classHits = (point) => {
      const { catalog: c, active: on } = latest.current
      const hits = {}
      const ls = c.layers.filter((l) => l.kind === 'choropleth' && l.ramp && on.has(l.id) && m.getLayer(fillId(l)))
      if (ls.length) {
        const f = m.queryRenderedFeatures(point, { layers: ls.map(fillId) })[0]
        const l = f && ls.find((x) => fillId(x) === f.layer.id)
        const v = l ? f.properties?.[l.property] : null
        if (l && typeof v === 'number') hits[l.id] = classIndex(l.ramp, v)
      }
      const node = nodeHit(point)
      const v = node ? node.feature.properties?.[node.layer.property] : null
      if (node && typeof v === 'number') hits[node.layer.id] = classIndex(node.layer.ramp, v)
      // the stretch under the pointer (not under the isochrone mode); one legend and one class focus serve all the layers: the first one on
      const ln = node || latest.current.isoOn ? null : lineHit(point)
      const lead = latest.current.catalog.layers.find((l) => l.kind === 'lines' && latest.current.active.has(l.id))
      if (ln && lead && typeof ln.hit.cls === 'number' && ln.hit.cls >= 0) hits[lead.id] = ln.hit.cls
      return { hits, node: !!node, line: ln }
    }
    // a small tooltip over a coloured cell: the class (the tiles carry only the class, so no value is invented) and the unit
    const hideTip = () => { if (tip.current) { tip.current.remove(); tip.current = null } }
    const showTip = (e, hits) => {
      const { catalog: c, active: on } = latest.current
      const l = c.layers.find((x) => x.kind === 'choropleth' && x.ramp && on.has(x.id))
      if (!l || !window.matchMedia('(hover: hover)').matches) return hideTip()
      let label = null
      if (hits[l.id] != null) label = rampLegend(l.ramp, '')[hits[l.id]]?.label
      else if (m.getLayer(`${l.id}:nodata`) && m.queryRenderedFeatures(e.point, { layers: [`${l.id}:nodata`] }).length) label = l.nodata_label || 'brak danych o rozkładach'
      if (!label) return hideTip()
      if (!tip.current) tip.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: 'cell-tip', offset: 12, maxWidth: '260px', focusAfterOpen: false })
      const root = document.createElement('div')
      const b = document.createElement('b')
      b.textContent = label
      root.appendChild(b)
      if (hits[l.id] != null && l.unit) {
        const u = document.createElement('small')
        u.textContent = l.unit
        root.appendChild(u)
      }
      tip.current.setLngLat(e.lngLat).setDOMContent(root).addTo(m)
    }
    // the one tooltip of a speed feature (name, speed with its +-1 min interval, trips an hour); the cell tooltip yields to it
    const hideLineTip = () => { if (ltip.current) { ltip.current.remove(); ltip.current = null } }
    const showLineTip = (e, line) => {
      if (!window.matchMedia('(hover: hover)').matches) return hideLineTip()
      hideTip()
      if (!ltip.current) ltip.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: 'seg-tip-pop', offset: 14, maxWidth: '280px', focusAfterOpen: false })
      ltip.current.setLngLat(e.lngLat).setDOMContent(renderLineTip(tipModel(line.hit.properties || {}, line.layer.band))).addTo(m)
    }
    m.on('mousemove', (e) => {
      const { hits, node, line } = classHits(e.point)
      const cityId = boundaryHits(e.point).find((f) => known(f.properties?.id))?.properties?.id ?? latest.current.cityAt?.(e.lngLat.lng, e.lngLat.lat)
      const isoHere = latest.current.isoOn && latest.current.selectedId && cityId === latest.current.selectedId
      m.getCanvas().style.cursor = node || line ? 'pointer' : isoHere ? 'crosshair' : cityId ? 'pointer' : ''
      latest.current.onHot?.(node || line ? null : cityId ?? null)
      latest.current.onLineHover?.(line ? { id: line.hit.id, keys: line.hit.keys } : null)
      if (line && !latest.current.inset) showLineTip(e, line)
      else { hideLineTip(); showTip(e, hits) }
      const ids = latest.current.catalog.layers.filter((l) => l.ramp && latest.current.active.has(l.id)).map((l) => l.id)
      setFocuses((f) => hoverOnMap(f, ids, hits))
    })
    m.on('mouseout', () => {
      hideTip()
      hideLineTip()
      setFocuses((f) => leaveMap(f))
      latest.current.onHot?.(null)
      latest.current.onLineHover?.(null)
    })
    m.on('remove', closePopup)

    const ro = new ResizeObserver(() => m.resize())
    ro.observe(box.current)
    return () => {
      document.removeEventListener('keydown', onEscape, true)
      dead = true
      ro.disconnect()
      m.remove()
      map.current = null
      setReady(null)
    }
  }, [])

  // layers on and off, selection outline
  useEffect(() => {
    if (!ready) return
    try {
      syncOverlays(ready, catalog.layers, active, selectedId, hot, outside)
      // the isochrone bands go on top of the value layers, just under the city outlines
      const outline = catalog.layers.find((l) => l.kind === 'boundary' && ready.getLayer(fillId(l)))
      syncIsochrones(ready, isoLayers, outline ? fillId(outline) : undefined)
    } catch (e) {
      console.warn('map layers:', e)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, catalog, active, selectedId, outside, isoLayers])

  // the lit city: outline only, no restacking
  useEffect(() => {
    if (ready) applyHot(ready, catalog.layers, hot)
  }, [ready, catalog, active, hot])

  // a layer that was switched off takes its popup with it (its highlighting goes in useFocuses)
  useEffect(() => {
    if (popup.current && !active.has(popup.current.layerId)) {
      popup.current.remove()
      popup.current = null
    }
  }, [active])

  // hovered and pinned classes stay at full strength, the rest fade
  useEffect(() => {
    if (!ready) return
    try {
      for (const l of catalog.layers) {
        if (l.kind === 'points' && l.ramp) {
          applyFocus(ready, l, emphasised(focusOf(focuses, l.id), l.id))
          continue
        }
        if (l.kind !== 'choropleth' || !l.ramp || !ready.getLayer(fillId(l))) continue
        const strong = emphasised(focusOf(focuses, l.id), l.id)
        ready.setPaintProperty(fillId(l), 'fill-opacity', focusOpacity(l.property, l.ramp, strong, (l.opacity ?? 0.8) * (isoLayers ? 0.55 : 1)))
        if (ready.getLayer(`${l.id}:nodata`)) {
          ready.setPaintProperty(`${l.id}:nodata`, 'fill-opacity', strong.size ? 0.25 : 0.9)
        }
      }
    } catch (e) {
      console.warn('map focus:', e)
    }
  }, [ready, catalog, active, selectedId, focuses, isoLayers])

  // the speed stretches: band, the legend's class focus (one for all the layers, that of the first on), the pinned lines of the table and the lit stretch
  useEffect(() => {
    if (!ready) return
    try {
      const ls = catalog.layers.filter((l) => l.kind === 'lines' && active.has(l.id))
      const lead = ls[0]
      for (const l of ls) {
        applyLines(ready, l, l.band, { classes: emphasised(focusOf(focuses, lead.id), lead.id), match: linePin, hot: lineHot, sel: lineSel?.[l.id] || null })
      }
    } catch (e) {
      console.warn('map lines:', e)
    }
  }, [ready, catalog, active, selectedId, focuses, lineHot, linePin, lineSel, loading])

  // a new selection of speed features stays in view: clear of the panel on the right (or the sheet at the bottom)
  useEffect(() => {
    if (!ready || !selBounds || inset) return undefined
    const t = setTimeout(() => {
      try { ensureVisible(ready, selBounds, document.querySelector('.seg-panel .kit-details')) } catch (e) { console.warn('map selection:', e) }
    }, 60)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, selN, inset])

  // the stop area whose card is open: its stops, walking paths and crossings on the map, the map flies to it
  useEffect(() => {
    if (!ready) return
    if (!detailNode) { clearNodeDetail(ready); return }
    showNodeDetail(ready, detailNode, ANCHOR_LABELS)
    const b = detailBounds(detailNode)
    if (b) ready.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: { top: 60, left: 40, right: 40, bottom: 60 }, maxZoom: 17, duration: 700 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, detailNode])
  useEffect(() => { if (ready) setHotPath(ready, hotPath) }, [ready, hotPath, detailNode])

  // fly to a stop area and open its popup when asked: {layer, props, coordinates, n}
  useEffect(() => {
    if (!ready || !nodeRequest) return
    const { layer, props, coordinates } = nodeRequest
    let done = false
    const open = () => {
      if (done) return
      done = true
      showPopup.current?.({ layer, feature: { properties: props, geometry: { coordinates } } })
    }
    // the popup is placed against the map as it will be once the flight is over
    ready.once('moveend', open)
    const t = setTimeout(open, 1600)
    ready.flyTo({ center: coordinates, zoom: Math.max(ready.getZoom(), 14), duration: 900, essential: true })
    return () => { clearTimeout(t); ready.off('moveend', open) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, nodeRequest])

  // fly to an agglomeration when asked: {bbox, animate, n}
  useEffect(() => {
    if (!ready || !fit) return
    ready.resize()   // the box may have just changed size (the dock moved): fit to what is there now
    ready.fitBounds(
      [[fit.bbox[0], fit.bbox[1]], [fit.bbox[2], fit.bbox[3]]],
      {
        padding: padNow(ready.getContainer(), fitPad),
        duration: fit.animate ? 1200 : 0,
        maxZoom: 12,
      },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, fit])

  const shown = catalog.layers.filter((l) => l.status === 'ready' && active.has(l.id))
  return (
    <div className="kit-map-wrap">
      <div ref={box} className="kit-map" />
      {mapError && <div className="map-error">Nie udało się uruchomić mapy: {mapError}</div>}
      {!inset && side}
      <Legend
        layers={shown} focuses={focuses} open={legendOpen} onOpen={onLegendOpen} shares={legendShares} loading={loading} extra={legendExtra}
        onHover={focus.onHover} onToggle={focus.onToggle} onClear={focus.onClear}
      />
    </div>
  )
}
