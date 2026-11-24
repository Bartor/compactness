import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import { buildStyle, hatchImage } from './mapStyle'
import { applyHot, fillId, syncOverlays } from './mapLayers'
import { classIndex, focusOpacity, rampLegend } from './ramp'
import { emphasised, focusOf, hoverOnMap, leaveMap } from './classFocus'
import { applyFocus, pointLayerIds } from './pointLayers'
import { nodePopupModel, renderNodePopup } from './nodePopup'
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
const POLAND = { center: [19.4, 52.1], zoom: 5.6 }
const isPhone = () => window.matchMedia('(max-width: 760px)').matches

// Desktop padding for fitBounds: the page passes it (`fitPad`), clear of the legend in the corner. The dock is not
// in it: it sits under the map and the map box already ends above it.
const DEFAULT_PAD = { top: 40, left: 40, right: 40, bottom: 40 }

// The kit's .kit-map-wrap supplies the sizing: a flex child that fills what
// the sidebar leaves, and the whole screen behind the sheets on phones.
export default function MapView({
  catalog, active, selectedId, hot, onHot, onSelect, fit, fitPad = DEFAULT_PAD, focus, nodeRequest, outside = null,
  legendOpen, onLegendOpen, legendShares, cityAt, onMoved, initialView = null,
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
  latest.current = { catalog, onSelect, active, onHot, cityAt, onMoved }
  const [loading, setLoading] = useState(false)   // tiles of a layer are still coming
  const tip = useRef(null)

  useEffect(() => {
    registerPmtiles()
    let m
    try {
      m = new maplibregl.Map({
        container: box.current,
        style: buildStyle(),
        center: initialView ? [initialView.lon, initialView.lat] : POLAND.center,
        zoom: initialView ? initialView.zoom : POLAND.zoom,
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
    const openPopup = ({ layer, feature }) => {
      closePopup()
      const content = renderNodePopup(nodePopupModel(feature.properties || {}, layer.timetable_date))
      // a popup taller than the map would stick out under the panel: it scrolls inside instead
      content.style.maxHeight = `${Math.max(160, Math.min(420, m.getContainer().clientHeight - 110))}px`
      const p = new maplibregl.Popup({ maxWidth: 'none', className: 'node-popup-wrap', focusAfterOpen: false, offset: 8 })
        .setLngLat(feature.geometry.coordinates.slice())
        .setDOMContent(content)
        .addTo(m)
      p.layerId = layer.id
      p.on('close', () => { if (popup.current === p) popup.current = null })
      popup.current = p
      // the popup must be fully visible: pan the map by what sticks out of it
      setTimeout(() => {
        const el = p.getElement()
        if (!el) return
        const r = el.getBoundingClientRect()
        const b = m.getContainer().getBoundingClientRect()
        const M = 14
        const dx = r.left < b.left + M ? r.left - b.left - M : r.right > b.right - M ? r.right - b.right + M : 0
        const dy = r.top < b.top + M ? r.top - b.top - M : r.bottom > b.bottom - M ? r.bottom - b.bottom + M : 0
        if (dx || dy) m.panBy([dx, dy], { duration: 250 })
      }, 300)
    }
    showPopup.current = openPopup
    // Escape closes the popup first (the nearest thing); the page's other Escape handlers then do not run
    const onEscape = (e) => { if (e.key === 'Escape' && popup.current) { e.stopPropagation(); closePopup() } }
    document.addEventListener('keydown', onEscape, true)
    m.on('click', (e) => {
      // a click on a node opens its popup and leaves the selected agglomeration alone
      const node = nodeHit(e.point)
      if (node) {
        openPopup(node)
        return
      }
      const id = boundaryHits(e.point).find((f) => known(f.properties?.id))?.properties?.id ?? latest.current.cityAt?.(e.lngLat.lng, e.lngLat.lat)
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
      return { hits, node: !!node }
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
    m.on('mousemove', (e) => {
      const { hits, node } = classHits(e.point)
      const cityId = boundaryHits(e.point).find((f) => known(f.properties?.id))?.properties?.id ?? latest.current.cityAt?.(e.lngLat.lng, e.lngLat.lat)
      m.getCanvas().style.cursor = node || cityId ? 'pointer' : ''
      latest.current.onHot?.(node ? null : cityId ?? null)
      showTip(e, hits)
      const ids = latest.current.catalog.layers.filter((l) => l.ramp && latest.current.active.has(l.id)).map((l) => l.id)
      setFocuses((f) => hoverOnMap(f, ids, hits))
    })
    m.on('mouseout', () => {
      hideTip()
      setFocuses((f) => leaveMap(f))
      latest.current.onHot?.(null)
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
    } catch (e) {
      console.warn('map layers:', e)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, catalog, active, selectedId, outside])

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
        ready.setPaintProperty(fillId(l), 'fill-opacity', focusOpacity(l.property, l.ramp, strong, l.opacity ?? 0.8))
        if (ready.getLayer(`${l.id}:nodata`)) {
          ready.setPaintProperty(`${l.id}:nodata`, 'fill-opacity', strong.size ? 0.25 : 0.9)
        }
      }
    } catch (e) {
      console.warn('map focus:', e)
    }
  }, [ready, catalog, active, selectedId, focuses])

  // fly to a stop area and open its popup when asked: {layer, props, coordinates, n}
  useEffect(() => {
    if (!ready || !nodeRequest) return
    const { layer, props, coordinates } = nodeRequest
    ready.flyTo({ center: coordinates, zoom: Math.max(ready.getZoom(), 14), duration: 900, essential: true })
    showPopup.current?.({ layer, feature: { properties: props, geometry: { coordinates } } })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, nodeRequest])

  // fly to an agglomeration when asked: {bbox, animate, n}
  useEffect(() => {
    if (!ready || !fit) return
    const phone = isPhone()
    ready.resize()   // the box may have just changed size (the dock moved): fit to what is there now
    ready.fitBounds(
      [[fit.bbox[0], fit.bbox[1]], [fit.bbox[2], fit.bbox[3]]],
      {
        padding: phone ? { top: 40, left: 20, right: 20, bottom: 120 } : fitPad,
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
      <Legend
        layers={shown} focuses={focuses} open={legendOpen} onOpen={onLegendOpen} shares={legendShares} loading={loading}
        onHover={focus.onHover} onToggle={focus.onToggle} onClear={focus.onClear}
      />
    </div>
  )
}
