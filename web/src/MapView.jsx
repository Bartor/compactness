import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import { buildStyle, hatchImage } from './mapStyle'
import { fillId, syncOverlays } from './mapLayers'
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

  // what the long-lived map handlers need to see
  latest.current = { catalog, onSelect }

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
    m.on('mousemove', (e) => {
      m.getCanvas().style.cursor = boundaryHits(e.point).some((f) => known(f.properties?.id)) ? 'pointer' : ''
    })

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

  // fly to an agglomeration when asked: {bbox, animate, n}
  useEffect(() => {
    if (!ready || !fit) return
    const phone = isPhone()
    ready.fitBounds(
      [[fit.bbox[0], fit.bbox[1]], [fit.bbox[2], fit.bbox[3]]],
      {
        padding: phone ? { top: 40, left: 20, right: 20, bottom: 120 }
          : { top: 40, left: 40, right: detailsOpen && window.innerWidth > 1100 ? 460 : 40, bottom: 40 },
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
      <Legend layers={shown} />
    </div>
  )
}
