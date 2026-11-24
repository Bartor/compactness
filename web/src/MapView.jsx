import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import { buildStyle, hatchImage } from './mapStyle'
import { fillId, syncOverlays } from './mapLayers'
import { classIndex, focusOpacity } from './ramp'
import { EMPTY_FOCUS, clearPinned, emphasised, hoverClass, pruneFocus, togglePinned } from './classFocus'
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

const POLAND = { center: [19.4, 52.1], zoom: 5.6 }
const isPhone = () => window.matchMedia('(max-width: 760px)').matches

// Desktop padding for fitBounds: clear of the details panel on the right and, when the map is wide enough to
// leave the area a readable size, of the legend in the bottom-left corner.
const LEGEND_W = 320
function fitPadding(mapWidth, detailsOpen) {
  const right = detailsOpen ? 460 : 40
  const left = mapWidth - right - LEGEND_W >= 360 ? LEGEND_W : 40
  return { top: 40, left, right, bottom: 40 }
}

// The kit's .kit-map-wrap supplies the sizing: a flex child that fills what
// the sidebar leaves, and the whole screen behind the sheets on phones.
export default function MapView({ catalog, active, selectedId, onSelect, fit, detailsOpen }) {
  const box = useRef(null)
  const map = useRef(null)
  const latest = useRef({})
  // the map object once its style has loaded; the object itself, so that a map
  // removed by a StrictMode remount can never be mistaken for the live one
  const [ready, setReady] = useState(null)
  const [mapError, setMapError] = useState(null)
  // colour classes hovered or pinned, shared by the legend and the map (classFocus.js)
  const [focus, setFocus] = useState(EMPTY_FOCUS)

  // what the long-lived map handlers need to see
  latest.current = { catalog, onSelect, active }

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
    m.on('click', (e) => {
      const hit = boundaryHits(e.point).find((f) => known(f.properties?.id))
      // from the whole-country view an area is a speck: tell the app, so it can zoom in
      if (hit) latest.current.onSelect(hit.properties.id, m.getZoom() < 7.5)
    })
    // the value-layer class under the pointer: {layerId, index} or null
    const classHit = (point) => {
      const { catalog: c, active: on } = latest.current
      const ls = c.layers.filter((l) => l.kind === 'choropleth' && l.ramp && on.has(l.id) && m.getLayer(fillId(l)))
      if (!ls.length) return null
      const f = m.queryRenderedFeatures(point, { layers: ls.map(fillId) })[0]
      const l = f && ls.find((x) => fillId(x) === f.layer.id)
      const v = l ? f.properties?.[l.property] : null
      return typeof v === 'number' ? { layerId: l.id, index: classIndex(l.ramp, v) } : null
    }
    m.on('mousemove', (e) => {
      m.getCanvas().style.cursor = boundaryHits(e.point).some((f) => known(f.properties?.id)) ? 'pointer' : ''
      const hit = classHit(e.point)
      setFocus((f) => hoverClass(f, hit ? hit.layerId : f.layerId, hit ? hit.index : null, 'map'))
    })
    m.on('mouseout', () => setFocus((f) => hoverClass(f, f.layerId, null)))

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
      syncOverlays(ready, catalog.layers, active, selectedId)
    } catch (e) {
      console.warn('map layers:', e)
    }
  }, [ready, catalog, active, selectedId])

  // a layer that was switched off takes its highlighting with it
  useEffect(() => setFocus((f) => pruneFocus(f, active)), [active])

  // hovered and pinned classes stay at full strength, the rest fade
  useEffect(() => {
    if (!ready) return
    try {
      for (const l of catalog.layers) {
        if (l.kind !== 'choropleth' || !l.ramp || !ready.getLayer(fillId(l))) continue
        const strong = emphasised(focus, l.id)
        ready.setPaintProperty(fillId(l), 'fill-opacity', focusOpacity(l.property, l.ramp, strong, l.opacity ?? 0.8))
        if (ready.getLayer(`${l.id}:nodata`)) {
          ready.setPaintProperty(`${l.id}:nodata`, 'fill-opacity', strong.size ? 0.25 : 0.9)
        }
      }
    } catch (e) {
      console.warn('map focus:', e)
    }
  }, [ready, catalog, active, selectedId, focus])

  // fly to an agglomeration when asked: {bbox, animate, n}
  useEffect(() => {
    if (!ready || !fit) return
    const phone = isPhone()
    ready.fitBounds(
      [[fit.bbox[0], fit.bbox[1]], [fit.bbox[2], fit.bbox[3]]],
      {
        padding: phone ? { top: 40, left: 20, right: 20, bottom: 120 }
          : fitPadding(box.current?.clientWidth || 0, detailsOpen && window.innerWidth > 1100),
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
        layers={shown} focus={focus}
        onHover={(id, i) => setFocus((f) => hoverClass(f, id, i))}
        onToggle={(id, i) => setFocus((f) => togglePinned(f, id, i))}
        onClear={(id) => setFocus((f) => clearPinned(f, id))}
      />
    </div>
  )
}
