import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import { buildStyle, hatchImage } from './mapStyle'
import { applyHot, fillId, syncOverlays } from './mapLayers'
import { classIndex, focusOpacity } from './ramp'
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

// Desktop padding for fitBounds: clear of the details panel on the right (560 px wide; the legend is in the sidebar).
const fitPadding = (detailsOpen) => ({ top: 40, left: 40, right: detailsOpen ? 600 : 40, bottom: 40 })

// The kit's .kit-map-wrap supplies the sizing: a flex child that fills what
// the sidebar leaves, and the whole screen behind the sheets on phones.
export default function MapView({
  catalog, active, selectedId, hot, onHot, onSelect, fit, detailsOpen, focus, nodeRequest, sharesOf,
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
  latest.current = { catalog, onSelect, active, onHot }

  useEffect(() => {
    registerPmtiles()
    let m
    try {
      m = new maplibregl.Map({
        container: box.current,
        style: buildStyle(),
        center: POLAND.center,
        zoom: POLAND.zoom,
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
    let dead = false
    m.touchZoomRotate.disableRotation()
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    m.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left')
    // Layer attributions come with their sources, and OpenFreeMap's own with the
    // basemap's TileJSON; this one is always there.
    m.addControl(new maplibregl.AttributionControl({
      compact: isPhone() || undefined,
      customAttribution: [
        '© współtwórcy <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
      ],
    }), 'bottom-right')

    m.on('load', () => {
      if (dead) return
      m.addImage('hatch', hatchImage(), { pixelRatio: 2 })
      setReady(m)
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
      const p = new maplibregl.Popup({ maxWidth: 'none', className: 'node-popup-wrap', focusAfterOpen: false, offset: 8 })
        .setLngLat(feature.geometry.coordinates.slice())
        .setDOMContent(renderNodePopup(nodePopupModel(feature.properties || {}, layer.timetable_date)))
        .addTo(m)
      p.layerId = layer.id
      p.on('close', () => { if (popup.current === p) popup.current = null })
      popup.current = p
    }
    showPopup.current = openPopup
    m.on('click', (e) => {
      // a click on a node opens its popup and leaves the selected agglomeration alone
      const node = nodeHit(e.point)
      if (node) {
        openPopup(node)
        return
      }
      const hit = boundaryHits(e.point).find((f) => known(f.properties?.id))
      // from the whole-country view an area is a speck: tell the app, so it can zoom in
      if (hit) latest.current.onSelect(hit.properties.id, m.getZoom() < 7.5)
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
    m.on('mousemove', (e) => {
      const { hits, node } = classHits(e.point)
      const city = boundaryHits(e.point).find((f) => known(f.properties?.id))
      m.getCanvas().style.cursor = node || city ? 'pointer' : ''
      latest.current.onHot?.(node ? null : city?.properties?.id ?? null)
      const ids = latest.current.catalog.layers.filter((l) => l.ramp && latest.current.active.has(l.id)).map((l) => l.id)
      setFocuses((f) => hoverOnMap(f, ids, hits))
    })
    m.on('mouseout', () => {
      setFocuses((f) => leaveMap(f))
      latest.current.onHot?.(null)
    })
    m.on('remove', closePopup)

    const ro = new ResizeObserver(() => m.resize())
    ro.observe(box.current)
    return () => {
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
      syncOverlays(ready, catalog.layers, active, selectedId, hot)
    } catch (e) {
      console.warn('map layers:', e)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, catalog, active, selectedId])

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
    ready.fitBounds(
      [[fit.bbox[0], fit.bbox[1]], [fit.bbox[2], fit.bbox[3]]],
      {
        padding: phone ? { top: 40, left: 20, right: 20, bottom: 120 }
          : fitPadding(detailsOpen && window.innerWidth > 1100),
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
        layers={shown} focuses={focuses}
        onHover={focus.onHover} onToggle={focus.onToggle} onClear={focus.onClear} sharesOf={sharesOf}
      />
    </div>
  )
}
